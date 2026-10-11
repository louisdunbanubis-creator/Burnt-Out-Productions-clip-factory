const REPO = "louisdunbanubis-creator/Burnt-Out-Productions-clip-factory";
const WORKFLOW = "render.yml";

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" }
  });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname === "/api/run") {
      if (request.method !== "POST") return json({ error: "Use POST." }, 405);
      const origin = request.headers.get("Origin");
      if (origin && origin !== url.origin) return json({ error: "Request origin rejected." }, 403);
      if (!env.GITHUB_TOKEN || !env.DASHBOARD_PIN) {
        return json({ error: "Dashboard connection is not configured yet. Add GITHUB_TOKEN and DASHBOARD_PIN as Cloudflare Worker secrets." }, 503);
      }

      let body;
      try { body = await request.json(); } catch { return json({ error: "Please submit the form again." }, 400); }
      if (typeof body.pin !== "string" || body.pin.length < 1 || body.pin !== env.DASHBOARD_PIN) {
        return json({ error: "Dashboard PIN is incorrect." }, 401);
      }
      if (body.rights_confirmed !== true) return json({ error: "Confirm that you have the rights to reuse this video." }, 400);
      if (!["youtube", "direct_mp4"].includes(body.source_type)) return json({ error: "Choose YouTube link or direct MP4 URL." }, 400);
      if (!["cars", "construction", "podcasts", "sports", "interesting"].includes(body.niche)) return json({ error: "Choose a valid niche." }, 400);
      if (!["original", "replace", "mix"].includes(body.narration_mode)) return json({ error: "Choose a valid narration mode." }, 400);

      const source = String(body.source_url || "").trim();
      let parsed;
      try { parsed = new URL(source); } catch { return json({ error: "Paste a valid video URL." }, 400); }
      if (parsed.protocol !== "https:") return json({ error: "For safety, the video URL must start with https://." }, 400);
      if (source.length > 2000) return json({ error: "The video URL is too long." }, 400);

      const maxClips = Number(body.max_clips);
      const duration = Number(body.target_duration);
      if (!Number.isInteger(maxClips) || maxClips < 1 || maxClips > 10) return json({ error: "Clip count must be between 1 and 10." }, 400);
      if (!Number.isInteger(duration) || duration < 15 || duration > 180) return json({ error: "Montage length must be 15–180 seconds." }, 400);

      const payload = {
        ref: "main",
        inputs: {
          source_type: body.source_type,
          source_url: source,
          rights_confirmed: "true",
          niche: body.niche,
          max_clips: String(maxClips),
          target_duration: String(duration),
          hook: String(body.hook || "").trim().slice(0, 180),
          narration_mode: body.narration_mode
        }
      };

      const gh = await fetch(`https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}/dispatches`, {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${env.GITHUB_TOKEN}`,
          "Accept": "application/vnd.github+json",
          "X-GitHub-Api-Version": "2022-11-28",
          "Content-Type": "application/json",
          "User-Agent": "Burnt-Out-Productions-Clip-Factory"
        },
        body: JSON.stringify(payload)
      });
      if (!gh.ok) {
        const details = (await gh.text()).slice(0, 500);
        return json({ error: `GitHub could not start the workflow (HTTP ${gh.status}). Check that the token has Actions: write access and the workflow is enabled.`, details }, 502);
      }
      return json({
        ok: true,
        message: "GitHub accepted the workflow dispatch. Your run may take a few moments to appear.",
        actions_url: `https://github.com/${REPO}/actions/workflows/${WORKFLOW}`
      }, 202);
    }

    return env.ASSETS.fetch(request);
  }
};
