import json
import os
import subprocess
from pathlib import Path

def run(cmd):
    print("$", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)

source = os.environ["SOURCE_FILE"]
output = os.environ.get("OUTPUT_FILE", "clip.mp4")
start = os.environ.get("START", "00:00:00")
duration = os.environ["DURATION"]
hook = os.environ.get("HOOK", "").strip()

vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"

if hook:
    safe = hook.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'").replace("%", "\\%")
    vf += ",drawtext=text='" + safe + "':x=(w-text_w)/2:y=120:fontsize=64:fontcolor=white:borderw=4:bordercolor=black:box=1:boxcolor=black@0.35:boxborderw=20"

run([
    "ffmpeg","-y","-ss",start,"-i",source,"-t",duration,
    "-vf",vf,"-map","0:v:0","-map","0:a?","-c:v","libx264",
    "-preset","veryfast","-crf","20","-c:a","aac","-b:a","160k",
    "-movflags","+faststart",output
])

metadata = {
    "source": os.environ.get("SOURCE_URL",""),
    "rights_confirmed": os.environ.get("RIGHTS_CONFIRMED",""),
    "niche": os.environ.get("NICHE",""),
    "start": start,
    "duration": duration,
    "hook": hook,
    "output": output
}
Path("metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
