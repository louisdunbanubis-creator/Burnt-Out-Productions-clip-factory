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

const STORE_MAX_BYTES = 80 * 1024 * 1024;

function randomToken() {
  const bytes = crypto.getRandomValues(new Uint8Array(32));
  return [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
}
function ipv4Parts(host) {
  const match = /^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/.exec(host);
  if (!match) return null;
  const parts = match.slice(1).map(Number);
  return parts.some((n) => n > 255) ? null : parts;
}
function isPrivateIpv4(parts) {
  const a = parts[0], b = parts[1];
  if (a === 0 || a === 10 || a === 127 || a === 255) return true;
  if (a === 169 && b === 254) return true;
  if (a === 172 && b >= 16 && b <= 31) return true;
  if (a === 192 && b === 168) return true;
  if (a === 100 && b >= 64 && b <= 127) return true;
  return false;
}
function isBlockedHostname(hostname) {
  const host = String(hostname || "").toLowerCase().replace(/^\[|\]$/g, "").replace(/\.$/, "");
  if (!host || host === "localhost" || host.endsWith(".localhost") || host.endsWith(".local") || host.endsWith(".internal")) return true;
  if (host === "metadata.google.internal" || host === "0.0.0.0" || host === "::1" || host === "::") return true;
  if (!host.includes(".") && !host.includes(":")) return true;
  if (host.includes(":")) {
    const v6 = host.split("%")[0];
    if (v6 === "::1" || v6.startsWith("fe80:") || v6.startsWith("fc") || v6.startsWith("fd")) return true;
    const mapped = /^::ffff:(\d{1,3}(?:\.\d{1,3}){3})$/i.exec(v6);
    return mapped ? isBlockedHostname(mapped[1]) : false;
  }
  const parts = ipv4Parts(host);
  return parts ? isPrivateIpv4(parts) : false;
}
function isConverterHost(hostname) {
  const host = String(hostname || "").toLowerCase().replace(/^www\./, "");
  return ["ytmp3.gg", "ytmp3.nu", "y2mate.com", "ssyoutube.com", "savefrom.net"].some((name) => host === name || host.endsWith(`.${name}`));
}
function classifyYouTube(parsed) {
  const host = parsed.hostname.toLowerCase().replace(/^www\./, "");
  const youtube = host === "youtu.be" || host === "youtube.com" || host === "m.youtube.com" || host === "music.youtube.com" || host === "youtube-nocookie.com" || host.endsWith(".youtube.com");
  if (host === "googlevideo.com" || host.endsWith(".googlevideo.com")) {
    return { error: "Paste the YouTube watch link, not a playback address. This hub does not download those URLs. Send the watch link with the clip job, or upload an MP4 from your phone." };
  }
  if (!youtube) return null;
  let id = "";
  if (host === "youtu.be") id = parsed.pathname.split("/").filter(Boolean)[0] || "";
  else if (/^\/(shorts|embed|live|v)\//.test(parsed.pathname)) id = parsed.pathname.split("/")[2] || "";
  else if (parsed.pathname === "/watch" || parsed.pathname === "/watch/") id = parsed.searchParams.get("v") || "";
  if (!/^[A-Za-z0-9_-]{6,20}$/.test(id)) return { error: "That YouTube link needs a video id. Paste a watch, shorts, or youtu.be link." };
  parsed.hash = "";
  return { source_url: parsed.toString() };
}
function isDirectMp4(contentType, pathname) {
  const type = String(contentType || "").split(";")[0].trim().toLowerCase();
  if (type === "video/mp4" || type === "application/mp4") return true;
  return /\.(mp4|m4v)$/i.test(pathname) && ["", "application/octet-stream", "binary/octet-stream", "application/binary"].includes(type);
}
function otherVideo(contentType, pathname) {
  const type = String(contentType || "").split(";")[0].trim().toLowerCase();
  return type.startsWith("video/") || /\.(webm|mov|mkv|avi|m4v)$/i.test(pathname);
}
function capStream(stream, cap) {
  let seen = 0;
  return stream.pipeThrough(new TransformStream({
    transform(chunk, controller) {
      seen += chunk.byteLength;
      if (seen > cap) throw new Error("TOO_BIG");
      controller.enqueue(chunk);
    }
  }));
}
function passthroughMp4(source, message) {
  return json({ ok: true, mode: "direct_mp4", source_type: "direct_mp4", source_url: source, message });
}
async function fetchPublic(start) {
  let current = start;
  for (let hop = 0; hop < 4; hop++) {
    const parsed = new URL(current);
    if (parsed.protocol !== "https:" || parsed.username || parsed.password || isBlockedHostname(parsed.hostname)) {
      throw new Error("That link is not a public HTTPS video URL.");
    }
    const response = await fetch(parsed.toString(), {
      method: "GET",
      redirect: "manual",
      signal: AbortSignal.timeout(25000),
      headers: { "User-Agent": "Burnt-Out-Productions-Clip-Factory", "Accept": "video/mp4,video/*;q=0.8,*/*;q=0.1" }
    });
    if ([301, 302, 303, 307, 308].includes(response.status)) {
      const location = response.headers.get("Location");
      if (!location) throw new Error("The video link redirected without a destination.");
      current = new URL(location, parsed).toString();
      if (current.length > 2000) throw new Error("The video link is too long.");
      continue;
    }
    if (!response.ok) throw new Error(`The video link returned HTTP ${response.status}.`);
    return { response, finalUrl: parsed };
  }
  throw new Error("The video link redirected too many times.");
}
async function convertLink(request, env, pageUrl) {
  if (request.method !== "POST") return json({ error: "Use POST." }, 405);
  if (!env.DASHBOARD_PIN) return json({ error: "The dashboard connection needs a DASHBOARD_PIN Worker secret." }, 503);
  if (!checkPin(request, env)) return json({ error: "Dashboard PIN is incorrect." }, 401);
  let body;
  try { body = await request.json(); } catch { return json({ error: "Please submit the convert form again." }, 400); }
  if (body.rights_confirmed !== true) return json({ error: "Confirm that you have the rights to reuse this video." }, 400);
  const raw = String(body.url || "").trim();
  if (!raw || raw.length > 2000) return json({ error: "Paste a valid HTTPS video link." }, 400);
  let parsed;
  try { parsed = new URL(raw); } catch { return json({ error: "Paste a valid video link." }, 400); }
  if (parsed.protocol !== "https:") return json({ error: "The video link must use HTTPS." }, 400);
  if (parsed.username || parsed.password || isBlockedHostname(parsed.hostname)) return json({ error: "That link is not a public HTTPS video URL." }, 400);
  if (isConverterHost(parsed.hostname)) return json({ error: "Paste the YouTube link or a direct MP4 URL. This hub does not call converter sites." }, 400);
  const youtube = classifyYouTube(parsed);
  if (youtube) {
    if (youtube.error) return json({ error: youtube.error }, 400);
    return json({
      ok: true,
      mode: "youtube",
      source_type: "youtube",
      source_url: youtube.source_url,
      message: "YouTube link is ready in this hub. This page cannot download YouTube, because Cloudflare cannot run the player signature step. Tap Send to Clip Factory. GitHub Actions turns it into an MP4, then clips it. If that download is blocked, save an MP4 on your phone and choose Upload an MP4 from my phone."
    });
  }
  if (parsed.origin === pageUrl.origin && /^\/api\/video\/[a-zA-Z0-9-]{20,80}$/.test(parsed.pathname)) {
    return passthroughMp4(parsed.toString(), "That MP4 is already stored in this hub. The source link is filled in. Choose your clip settings and tap Send to Clip Factory.");
  }
  let fetched;
  try { fetched = await fetchPublic(parsed.toString()); }
  catch (e) {
    const timedOut = e && (e.name === "TimeoutError" || e.name === "AbortError");
    if (timedOut && isDirectMp4("", parsed.pathname)) {
      return passthroughMp4(parsed.toString(), "Copying that MP4 into hub storage took too long. The original file link is filled in instead. The clip job downloads it directly, up to 1.8 GB.");
    }
    return json({ error: e instanceof Error ? e.message : "Could not open that video link." }, 502);
  }
  const { response, finalUrl } = fetched;
  const contentType = response.headers.get("content-type") || "";
  const type = contentType.split(";")[0].trim().toLowerCase();
  if (type.startsWith("text/") || type === "application/xhtml+xml" || type === "application/json") {
    await response.body?.cancel();
    return json({ error: "That link opened a web page, not an MP4 file. Paste a YouTube watch link, or a direct HTTPS link to an .mp4 file." }, 400);
  }
  const namedMp4 = /\.(mp4|m4v)$/i.test(finalUrl.pathname);
  const typedMp4 = type === "video/mp4" || type === "application/mp4";
  const octetMp4 = namedMp4 && ["application/octet-stream", "binary/octet-stream", "application/binary"].includes(type);
  const canStore = typedMp4 || octetMp4;
  const canPassthrough = canStore || (namedMp4 && type === "");
  if (!canPassthrough) {
    await response.body?.cancel();
    if (otherVideo(contentType, finalUrl.pathname)) {
      return json({ error: "That file is not an MP4. This hub cannot transcode video inside Cloudflare. Upload an MP4 from your phone, or paste a YouTube link and send the job so GitHub Actions makes the MP4." }, 400);
    }
    return json({ error: "That link is not a direct MP4 file. Paste a YouTube link, or a URL that downloads an .mp4 file." }, 400);
  }
  const advertised = Number(response.headers.get("content-length"));
  if (Number.isFinite(advertised) && advertised < 1) {
    await response.body?.cancel();
    return json({ error: "That link did not return a video file." }, 400);
  }
  const overStoreCap = Number.isFinite(advertised) && advertised > STORE_MAX_BYTES;
  if (Number.isFinite(advertised) && advertised > MAX_VIDEO_BYTES) {
    await response.body?.cancel();
    return json({ error: "That video is over the 1.8 GB limit." }, 413);
  }
  if (!canStore || overStoreCap || !env.VIDEO_BUCKET) {
    await response.body?.cancel();
    const message = !env.VIDEO_BUCKET
      ? "Video storage is not connected, so this MP4 was not copied into the hub. The file link is filled in. The clip job downloads it directly, up to 1.8 GB."
      : !canStore
        ? "The server did not label this file as an MP4. The original link is filled in. The clip job downloads it directly, up to 1.8 GB."
        : "This MP4 is larger than 80 MB, so it was not copied into hub storage. The original file link is filled in. The clip job downloads it directly, up to 1.8 GB.";
    return passthroughMp4(finalUrl.toString(), message);
  }
  const id = crypto.randomUUID();
  const token = randomToken();
  const key = `videos/${id}.mp4`;
  const filename = decodeURIComponent(finalUrl.pathname.split("/").pop() || "source.mp4").slice(0, 180);
  try {
    await env.VIDEO_BUCKET.put(key, capStream(response.body, STORE_MAX_BYTES), {
      httpMetadata: { contentType: "video/mp4", cacheControl: "private, max-age=0, no-store" },
      customMetadata: { downloadToken: token, originalFilename: filename, size: Number.isFinite(advertised) ? String(advertised) : "streamed", source: "hub-convert" }
    });
  } catch (e) {
    try { await env.VIDEO_BUCKET.delete(key); } catch {}
    if (String(e && e.message || e).includes("TOO_BIG")) {
      return passthroughMp4(finalUrl.toString(), "This MP4 is larger than 80 MB, so it was not copied into hub storage. The original file link is filled in. The clip job downloads it directly, up to 1.8 GB.");
    }
    return json({ error: "Could not save that MP4 into hub storage. Paste the direct MP4 link in the video link field and send the job." }, 502);
  }
  const sourceUrl = `${pageUrl.origin}/api/video/${id}?token=${encodeURIComponent(token)}`;
  const sizeLabel = Number.isFinite(advertised) ? ` (${(advertised / 1048576).toFixed(1)} MB)` : "";
  return json({
    ok: true,
    mode: "stored_mp4",
    source_type: "direct_mp4",
    source_url: sourceUrl,
    message: `Saved a private MP4 in this hub${sizeLabel}. The source link below is filled in. Choose your clip settings and tap Send to Clip Factory.`
  });
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

      if (url.pathname === "/api/convert") return convertLink(request, env, url);

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
