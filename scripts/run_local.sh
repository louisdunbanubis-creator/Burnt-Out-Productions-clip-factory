#!/usr/bin/env bash
set -euo pipefail

# Local-video mode for Burnt Out Productions Clip Factory.
# Run from Terminal: bash scripts/run_local.sh "/path/to/your-video.mp4"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ $# -gt 0 ]]; then
  SOURCE_FILE="$1"
else
  printf "Path to your local video (you can drag the file into Terminal): "
  IFS= read -r SOURCE_FILE
fi

# Trim optional surrounding quotes from pasted paths.
SOURCE_FILE="${SOURCE_FILE%\"}"
SOURCE_FILE="${SOURCE_FILE#\"}"
SOURCE_FILE="${SOURCE_FILE%\'}"
SOURCE_FILE="${SOURCE_FILE#\'}"

if [[ ! -f "$SOURCE_FILE" ]]; then
  echo "Could not find that file. Check the path and try again."
  exit 1
fi
SOURCE_FILE="$(cd "$(dirname "$SOURCE_FILE")" && pwd)/$(basename "$SOURCE_FILE")"

printf "Do you own or have permission/lawful rights to reuse this video? Type yes to continue: "
read -r RIGHTS_CONFIRMATION
if [[ "$RIGHTS_CONFIRMATION" != "yes" ]]; then
  echo "Stopped. Only process footage you have rights to reuse."
  exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1 || ! command -v ffprobe >/dev/null 2>&1; then
  echo "FFmpeg is required. On a Mac with Homebrew, run: brew install ffmpeg"
  exit 1
fi
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is required. Install it from python.org or with Homebrew."
  exit 1
fi

printf "\nChoose a niche (cars, construction, podcasts, sports, interesting) [interesting]: "
read -r NICHE
NICHE="${NICHE:-interesting}"
case "$NICHE" in
  cars|construction|podcasts|sports|interesting) ;;
  *) echo "Unknown niche '$NICHE'; using interesting."; NICHE="interesting" ;;
esac

printf "Number of clips [5]: "
read -r MAX_CLIPS
MAX_CLIPS="${MAX_CLIPS:-5}"
printf "Target montage length in seconds [45]: "
read -r TARGET_DURATION
TARGET_DURATION="${TARGET_DURATION:-45}"
printf "Narration (original, replace, mix) [original]: "
read -r NARRATION_MODE
NARRATION_MODE="${NARRATION_MODE:-original}"
case "$NARRATION_MODE" in
  original|replace|mix) ;;
  *) echo "Unknown narration mode; using original."; NARRATION_MODE="original" ;;
esac
printf "Optional headline for every clip (leave blank for generated headlines): "
read -r HOOK

mkdir -p work output
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
.venv/bin/python -m pip install --upgrade pip
.venv/bin/pip install --upgrade openai-whisper

FONT_FILE="$ROOT/work/Anton-Regular.ttf"
if [[ ! -f "$FONT_FILE" ]]; then
  curl -L --fail --retry 3 -o "$FONT_FILE" https://raw.githubusercontent.com/google/fonts/main/ofl/anton/Anton-Regular.ttf
fi
mkdir -p "$HOME/Library/Fonts"
cp "$FONT_FILE" "$HOME/Library/Fonts/Anton-Regular.ttf"

if [[ "$NARRATION_MODE" == "replace" || "$NARRATION_MODE" == "mix" ]]; then
  .venv/bin/pip install --upgrade piper-tts
  PIPER_MODEL="$ROOT/work/en_US-lessac-medium.onnx"
  if [[ ! -f "$PIPER_MODEL" ]]; then
    curl -L --fail --retry 3 -o "$PIPER_MODEL" https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx
  fi
  if [[ ! -f "$PIPER_MODEL.json" ]]; then
    curl -L --fail --retry 3 -o "$PIPER_MODEL.json" https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json
  fi
else
  PIPER_MODEL="$ROOT/work/en_US-lessac-medium.onnx"
fi

echo "Measuring local video..."
SOURCE_DURATION="$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$SOURCE_FILE")"
echo "Extracting audio..."
ffmpeg -y -i "$SOURCE_FILE" -vn -ac 1 -ar 16000 -c:a pcm_s16le work/audio.wav
echo "Transcribing audio with Whisper (the first run downloads the model)..."
.venv/bin/whisper work/audio.wav --model base --language en --output_format json --output_dir work

echo "Finding candidate moments and preparing scripts..."
TRANSCRIPT_JSON="$ROOT/work/audio.json" \
SOURCE_DURATION="$SOURCE_DURATION" NICHE="$NICHE" MAX_CLIPS="$MAX_CLIPS" \
TARGET_DURATION="$TARGET_DURATION" GEMINI_API_KEY="${GEMINI_API_KEY:-}" \
.venv/bin/python scripts/analyze.py

echo "Rendering clips..."
SOURCE_FILE="$SOURCE_FILE" SOURCE_URL="local-file:$SOURCE_FILE" RIGHTS_CONFIRMED="$RIGHTS_CONFIRMATION" \
NICHE="$NICHE" HOOK="$HOOK" NARRATION_MODE="$NARRATION_MODE" PIPER_MODEL="$PIPER_MODEL" \
FONT_FILE="$FONT_FILE" PATH="$ROOT/.venv/bin:$PATH" \
ANALYSIS_FILE="$ROOT/work/analysis.json" TRANSCRIPT_JSON="$ROOT/work/audio.json" \
OUTPUT_FILE="$ROOT/output/best_moments_$NICHE.mp4" \
.venv/bin/python scripts/render.py

echo "Preparing vidIQ keyword research queue..."
ANALYSIS_FILE="$ROOT/work/analysis.json" OUTPUT_DIR="$ROOT/output" NICHE="$NICHE" \
SOURCE_URL="local-file:$SOURCE_FILE" \
.venv/bin/python scripts/vidiq_research.py

echo "Running live vidIQ research if VIDIQ_MCP_API_KEY is configured..."
VIDIQ_MCP_API_KEY="${VIDIQ_MCP_API_KEY:-}" \
VIDIQ_QUEUE_JSON="$ROOT/output/vidiq-research-queue.json" \
.venv/bin/python scripts/vidiq_mcp_research.py

echo
echo "Finished. Your files are in:"
open "$ROOT/output" 2>/dev/null || true
echo "$ROOT/output"
echo "Keep the original video until you've checked the finished clips."
