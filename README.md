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
10. Generates a per-clip vidIQ keyword research queue with candidate search phrases, draft titles, descriptions, and relevant tag suggestions.
11. Uploads MP4s, scripts, analysis, metadata, and the vidIQ research queue as a downloadable GitHub Actions artifact (available for 3 days).

## vidIQ keyword research (new)

Every cloud clip run creates `vidiq-research-queue.csv` and `vidiq-research-queue.json` inside the output artifact.

1. Open the finished GitHub Actions run and download its artifact.
2. Open the CSV in a spreadsheet, or use the JSON version.
3. For each clip, open [vidIQ Keyword Research](https://app.vidiq.com/) and search the suggested candidate phrases.
4. Compare vidIQ's displayed search-volume estimate, competition, and overall keyword score when available.
5. Choose a phrase that accurately matches the clip, favoring strong demand with lower competition. Do not use unrelated keywords just because their volume is high.
6. Fill in the blank metric/date fields in the research queue, then revise the draft title, description, and tags.
7. Have a human review the final metadata before publishing.

The workflow deliberately leaves vidIQ metrics blank until they are checked. It does not fabricate search volume or competition data. Candidate phrases are suggestions generated from the clip transcript and selected niche; they are not a substitute for vidIQ's live research. For the same keyword selection principles, see [docs/vidiq-keyword-research.md](docs/vidiq-keyword-research.md).

## Run it from iPhone

1. Open the Cloudflare dashboard and tap OPEN CLIP MAKER.
2. In GitHub Actions, choose Run workflow.
3. Paste a source URL and confirm your reuse rights.
4. Choose a niche, clip count, target montage duration, and narration mode.
5. Start the run. Open the completed run and download the artifact.
6. Open the vidIQ research queue in the artifact and complete the keyword check before publishing.

Choose original to keep the source audio. Choose replace to use generated narration instead, or mix to layer narration over the original audio. Piper TTS is open-source and the voice model is downloaded only when needed.

## Optional AI script refinement

To enable Gemini refinement, create a Gemini API key using its available free tier, then add it in GitHub repository Settings → Secrets and variables → Actions → New repository secret with the name GEMINI_API_KEY. Never paste the key into code or the website. If the key is missing, over quota, or the request fails, the workflow falls back to the free template-based script generator.

## Current limitations (important)

- Moment selection is transcript/keyword based. It is an automated first pass, not a guarantee of virality or a full visual understanding model.
- The generated script is based on what is actually said in the selected moment; it does not invent a new factual story.
- B-roll search phrases are included in scripts/metadata, but the current workflow does not yet fetch or insert B-roll footage automatically.
- vidIQ keyword candidates are generated automatically, but actual search-volume/competition verification remains a vidIQ research step; publishing is not automated from these metrics.
- Music is not automatically added yet. Use only music you own or are licensed to use.
- The default mode keeps original audio and does not generate voiceover. Choose replace or mix when you want Piper narration.
- Anton is the current open-license condensed display font substitute; it is not the exact RedthaProducer typeface.

## Free-first architecture

The workflow uses GitHub Actions, Whisper, FFmpeg, and optional Piper TTS. GitHub Actions usage and free-tier limits can change; check your account's current usage before processing large videos. AI script refinement is optional and depends on the free quota available from the selected provider.

## Rights gate

Only process footage you own, have permission/license to use, public-domain material, applicable Creative Commons material, or footage you are using in a lawful transformative/commentary workflow. A source being publicly viewable does not automatically grant reuse rights.

## Process a video saved on your Mac (no URL needed)

GitHub Actions runs on a separate cloud computer and cannot read files directly from your Mac. To process a local file without uploading it to a video site, use the local runner included in this repository.

1. Install [Homebrew](https://brew.sh/) if you do not already have it.
2. Open Terminal and install FFmpeg: `brew install ffmpeg`.
3. Download this repository to your Mac (GitHub's **Code → Download ZIP** works), unzip it, and open Terminal in the unzipped project folder.
4. Run: `bash scripts/run_local.sh`
5. When asked for the video path, drag your video file from Finder into Terminal and press Return. Or pass the path directly: `bash scripts/run_local.sh "/full/path/to/video.mp4"`.
6. Answer the prompts for niche, clip count, montage length, and narration mode. Results are saved in the project's `output/` folder.

The first run installs Whisper in a local Python virtual environment and downloads the transcription model, so it can take a while and needs an internet connection. Video analysis/rendering then happens on your Mac; longer videos need more time and free disk space. The default narration mode preserves the original audio. Replace/mix modes install Piper and download its voice model. Optional Gemini script refinement works if you set `GEMINI_API_KEY` in your Terminal environment.

Only process videos you own or have permission to reuse. The local runner does not upload your source video to GitHub; it downloads software/models as needed and writes finished files to `output/`.
