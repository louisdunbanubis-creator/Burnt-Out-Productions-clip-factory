const REPO = "louisdunbanubis-creator/Burnt-Out-Productions-clip-factory";
const WORKFLOW = "render.yml";
const MAX_VIDEO_BYTES = 1_800_000_000;
const CHUNK_BYTES = 8 * 1024 * 1024;

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" }
  });
}
function validId(value) { return /^[a-zA-Z0-9-]{20,80}$/.test(value || ""); }
function sameOrigin(request, url) {
  const origin = request.headers.get("Origin");
  return !origin || origin === url.origin;
}
function checkPin(request, env) {
  return Boolean(env.DASHBOARD_PIN && request.headers.get("x-dashboard-pin") === env.DASHBOARD_PIN);
}
async function dispatchWorkflow(env, body) {
  const source = String(body.source_url || "").trim();
  let parsed;
  try { parsed = new URL(source); } catch { return json({ error: "Paste a valid video URL or upload an MP4." }, 400); }
  if (parsed.protocol !== "https:") return json({ error: "The video URL must use HTTPS." }, 400);
  if (source.length > 2000) return json({ error: "The video URL is too long." }, 400);
  if (body.rights_confirmed !== true) return json({ error: "Confirm that you have the rights to reuse this video." }, 400);
  if (!["youtube", "direct_mp4"].includes(body.source_type)) return json({ error: "Choose YouTube link or direct MP4." }, 400);
  if (!["cars", "construction", "podcasts", "sports", "interesting"].includes(body.niche)) return json({ error: "Choose a valid niche." }, 400);
  if (!["original", "replace", "mix"].includes(body.narration_mode)) return json({ error: "Choose a valid narration mode." }, 400);
  const maxClips = Number(body.max_clips), duration = Number(body.target_duration);
  if (!Number.isInteger(maxClips) || maxClips < 1 || maxClips > 10) return json({ error: "Clip count must be between 1 and 10." }, 400);
  if (!Number.isInteger(duration) || duration < 15 || duration > 180) return json({ error: "Montage length must be 15–180 seconds." }, 400);
  const payload = { ref: "main", inputs: {
    source_type: body.source_type, source_url: source, rights_confirmed: "true",
    niche: body.niche, max_clips: String(maxClips), target_duration: String(duration),
    hook: String(body.hook || "").trim().slice(0, 180), narration_mode: body.narration_mode
  }};
  const gh = await fetch(`https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}/dispatches`, {
    method: "POST",
    headers: { "Authorization": `Bearer ${env.GITHUB_TOKEN}`, "Accept": "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28", "Content-Type": "application/json",
      "User-Agent": "Burnt-Out-Productions-Clip-Factory" },
    body: JSON.stringify(payload)
  });
  if (!gh.ok) {
    const details = (await gh.text()).slice(0, 500);
    return json({ error: `GitHub could not start the workflow (HTTP ${gh.status}). Check the token's Actions write permission and that the workflow is enabled.`, details }, 502);
  }
  return json({ ok: true, message: "GitHub accepted your job. It may take a few moments to appear.", actions_url: `https://github.com/${REPO}/actions/workflows/${WORKFLOW}` }, 202);
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname.startsWith("/api/")) {
      if (!sameOrigin(request, url)) return json({ error: "Request origin rejected." }, 403);

      if (url.pathname === "/api/run") {
        if (request.method !== "POST") return json({ error: "Use POST." }, 405);
        if (!env.GITHUB_TOKEN || !env.DASHBOARD_PIN) return json({ error: "The dashboard connection needs GITHUB_TOKEN and DASHBOARD_PIN Worker secrets." }, 503);
        if (!checkPin(request, env)) return json({ error: "Dashboard PIN is incorrect." }, 401);
        let body;
        try { body = await request.json(); } catch { return json({ error: "Please submit the form again." }, 400); }
        return dispatchWorkflow(env, body);
      }

      if (url.pathname === "/api/upload/chunk") {
        if (request.method !== "PUT") return json({ error: "Use PUT for upload chunks." }, 405);
        if (!env.VIDEO_BUCKET) return json({ error: "Video storage is not connected yet. Create the Cloudflare R2 bucket and add the VIDEO_BUCKET binding." }, 503);
        if (!env.DASHBOARD_PIN || !checkPin(request, env)) return json({ error: "Enter your correct dashboard PIN before uploading." }, 401);
        const id = url.searchParams.get("id"), part = Number(url.searchParams.get("part")), total = Number(url.searchParams.get("total"));
        if (!validId(id) || !Number.isInteger(part) || !Number.isInteger(total) || total < 1 || total > 230 || part < 0 || part >= total) return json({ error: "Invalid upload details." }, 400);
        const bytes = await request.arrayBuffer();
        if (!bytes.byteLength || bytes.byteLength > CHUNK_BYTES) return json({ error: "Upload chunk size is invalid. Please retry." }, 413);
        await env.VIDEO_BUCKET.put(`tmp/${id}/${String(part).padStart(4,"0")}`, bytes, { customMetadata: { uploadId: id, part: String(part), total: String(total) } });
        return json({ ok: true, part, total });
      }

      if (url.pathname === "/api/upload/finish") {
        if (request.method !== "POST") return json({ error: "Use POST to finish an upload." }, 405);
        if (!env.VIDEO_BUCKET || !env.DASHBOARD_PIN || !checkPin(request, env)) return json({ error: "Video storage or dashboard authorization is not configured." }, 401);
        let body;
        try { body = await request.json(); } catch { return json({ error: "Upload details were missing." }, 400); }
        const id = String(body.id || ""), token = String(body.token || ""), filename = String(body.filename || "source.mp4");
        const total = Number(body.total), size = Number(body.size);
        if (!validId(id) || !/^[a-zA-Z0-9_-]{40,100}$/.test(token) || !Number.isInteger(total) || total < 1 || total > 230 || !Number.isInteger(size) || size < 1 || size > MAX_VIDEO_BYTES) return json({ error: "Invalid upload details or file exceeds the 1.8 GB limit." }, 400);
        const key = `videos/${id}.mp4`;
        const multipart = await env.VIDEO_BUCKET.createMultipartUpload(key, {
          httpMetadata: { contentType: "video/mp4", cacheControl: "private, max-age=0, no-store" },
          customMetadata: { downloadToken: token, originalFilename: filename.slice(0,180), size: String(size) }
        });
        const parts = [];
        let observed = 0;
        try {
          for (let i = 0; i < total; i++) {
            const obj = await env.VIDEO_BUCKET.get(`tmp/${id}/${String(i).padStart(4,"0")}`);
            if (!obj) throw new Error(`Missing upload chunk ${i + 1} of ${total}. Please retry the upload.`);
            const data = await obj.arrayBuffer();
            observed += data.byteLength;
            const uploaded = await multipart.uploadPart(i + 1, data);
            parts.push({ partNumber: i + 1, etag: uploaded.etag });
          }
          if (observed !== size) throw new Error("Uploaded file size did not match the selected file.");
          await multipart.complete(parts);
          for (let i = 0; i < total; i++) await env.VIDEO_BUCKET.delete(`tmp/${id}/${String(i).padStart(4,"0")}`);
        } catch (e) {
          try { await multipart.abort(); } catch {}
          return json({ error: e instanceof Error ? e.message : "Could not finish uploading the MP4." }, 500);
        }
        return json({ ok: true, source_url: `${url.origin}/api/video/${id}?token=${encodeURIComponent(token)}`, filename: filename.slice(0,180), size });
      }

      const videoMatch = url.pathname.match(/^\/api\/video\/([a-zA-Z0-9-]{20,80})$/);
      if (videoMatch && (request.method === "GET" || request.method === "HEAD")) {
        if (!env.VIDEO_BUCKET) return json({ error: "Video storage is not connected." }, 503);
        const obj = await env.VIDEO_BUCKET.get(`videos/${videoMatch[1]}.mp4`);
        const token = url.searchParams.get("token") || "";
        if (!obj || !token || obj.customMetadata?.downloadToken !== token) return json({ error: "Video link is invalid or expired." }, 404);
        const headers = new Headers();
        obj.writeHttpMetadata(headers);
        headers.set("content-length", String(obj.size));
        headers.set("content-disposition", 'attachment; filename="source.mp4"');
        headers.set("cache-control", "private, no-store");
        headers.set("accept-ranges", "none");
        return new Response(request.method === "HEAD" ? null : obj.body, { status: 200, headers });
      }
      return json({ error: "API route not found." }, 404);
    }
    return env.ASSETS.fetch(request);
  }
};
