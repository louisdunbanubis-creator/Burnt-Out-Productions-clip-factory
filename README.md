# Burnt Out Productions Clip Factory

A free-first, iPhone-controlled video clipping pipeline. Heavy work runs in GitHub Actions; the website is the mobile control panel.

## What the workflow produces

1. Downloads a source URL only after you confirm you have the right to reuse it.
2. Transcribes the full video's English audio with Whisper.
3. Scores transcript moments against the chosen niche and engagement-language heuristics.
4. Selects non-overlapping moments, aiming toward your requested total duration.
5. Creates a hook, short script excerpt, call to action, and B-roll search suggestion for each moment.
6. Optionally refines hooks/scripts with Gemini when you add a GEMINI_API_KEY repository secret. Without the secret it falls back to free transcript-based templates.
7. Converts each moment to vertical 9:16, adds burned-in captions and a headline.
8. Saves every clip separately and stitches them into one montage.
9. Optionally creates Piper text-to-speech narration and either replaces the original audio or mixes narration over quieter source audio.
10. Uploads MP4s, scripts, analysis, and metadata as a downloadable GitHub Actions artifact (available for 3 days).

## Run it from iPhone

1. Open the Cloudflare dashboard and tap OPEN CLIP MAKER.
2. In GitHub Actions, choose Run workflow.
3. Paste a source URL and confirm your reuse rights.
4. Choose a niche, clip count, target montage duration, and narration mode.
5. Start the run. Open the completed run and download the artifact.

Choose original to keep the source audio. Choose replace to use generated narration instead, or mix to layer narration over the original audio. Piper TTS is open-source and the voice model is downloaded only when needed.

## Optional AI script refinement

To enable Gemini refinement, create a Gemini API key using its available free tier, then add it in GitHub repository Settings → Secrets and variables → Actions → New repository secret with the name GEMINI_API_KEY. Never paste the key into code or the website. If the key is missing, over quota, or the request fails, the workflow falls back to the free template-based script generator.

## Current limitations (important)

- Moment selection is transcript/keyword based. It is an automated first pass, not a guarantee of virality or a full visual understanding model.
- The generated script is based on what is actually said in the selected moment; it does not invent a new factual story.
- B-roll search phrases are included in scripts/metadata, but the current workflow does not yet fetch or insert B-roll footage automatically.
- Music is not automatically added yet. Use only music you own or are licensed to use.
- The default mode keeps original audio and does not generate voiceover. Choose replace or mix when you want Piper narration.
- Anton is the current open-license condensed display font substitute; it is not the exact RedthaProducer typeface.

## Free-first architecture

The workflow uses GitHub Actions, Whisper, FFmpeg, and optional Piper TTS. GitHub Actions usage and free-tier limits can change; check your account's current usage before processing large videos. AI script refinement is optional and depends on the free quota available from the selected provider.

## Rights gate

Only process footage you own, have permission/license to use, public-domain material, applicable Creative Commons material, or footage you are using in a lawful transformative/commentary workflow. A source being publicly viewable does not automatically grant reuse rights.
