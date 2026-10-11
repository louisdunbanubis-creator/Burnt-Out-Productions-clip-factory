import json, os, subprocess, shlex
from pathlib import Path

SOURCE = os.environ["SOURCE_FILE"]
OUTPUT = os.environ.get("OUTPUT_FILE", "output/best_moments.mp4")
NICHE = os.environ.get("NICHE", "interesting")
HOOK_OVERRIDE = os.environ.get("HOOK", "").strip()
NARRATION_MODE = os.environ.get("NARRATION_MODE", "original")
FONT = os.environ.get("FONT_FILE", "/usr/share/fonts/truetype/anton/Anton-Regular.ttf")
ANALYSIS = json.load(open(os.environ.get("ANALYSIS_FILE", "work/analysis.json"), encoding="utf-8"))
TRANSCRIPT = json.load(open(os.environ.get("TRANSCRIPT_JSON", "work/transcript.json"), encoding="utf-8"))
VOICE_MODEL = os.environ.get("PIPER_MODEL", "work/en_US-lessac-medium.onnx")

Path("work/rendered").mkdir(parents=True, exist_ok=True)
Path("output").mkdir(parents=True, exist_ok=True)

def run(cmd, input_text=None):
    print("$", " ".join(shlex.quote(str(x)) for x in cmd), flush=True)
    subprocess.run(cmd, check=True, input=input_text, text=input_text is not None)

def ass_escape(s):
    return s.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}").replace("\n", " ")

def ass_time(sec):
    h=int(sec//3600); m=int((sec%3600)//60); s=sec%60
    return f"{h}:{m:02d}:{s:05.2f}"

def write_ass(path, start, end):
    rows=["[Script Info]","ScriptType: v4.00+","PlayResX: 1080","PlayResY: 1920",
          "[V4+ Styles]","Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Alignment,MarginL,MarginR,MarginV,BorderStyle,Outline,Shadow",
          "Style: Brand,Anton,62,&H00FFFFFF,&H00FFFFFF,&H00000000,&H88000000,0,0,2,70,70,190,1,4,0",
          "[Events]","Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text"]
    for seg in TRANSCRIPT.get("segments", []):
        a=float(seg.get("start",0)); b=float(seg.get("end",0))
        if b<=start or a>=end: continue
        a=max(a,start)-start; b=min(b,end)-start
        txt=ass_escape(seg.get("text","").strip())
        if txt: rows.append(f"Dialogue: 0,{ass_time(a)},{ass_time(b)},Brand,,0,0,0,,{txt}")
    Path(path).write_text("\n".join(rows)+"\n", encoding="utf-8")

def make_voiceover(moment, idx):
    text = " ".join(x for x in [moment.get("script",""), moment.get("cta","")] if x).strip()
    voice_path = f"work/rendered/voiceover_{idx}.wav"
    if not text:
        raise RuntimeError("No script text exists for voiceover.")
    run(["piper", "--model", VOICE_MODEL, "--output_file", voice_path], input_text=text)
    return voice_path

clips=[]
for idx, moment in enumerate(ANALYSIS.get("moments", []), 1):
    start=float(moment["start"]); end=float(moment["end"]); duration=max(1,end-start)
    ass=f"work/rendered/captions_{idx}.ass"
    write_ass(ass,start,end)
    out=f"output/clip_{idx:02d}_{NICHE}.mp4"
    hook=HOOK_OVERRIDE or moment.get("hook","")
    vf=f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,subtitles={ass}"
    if hook:
        safe=hook.replace("\\","\\\\").replace(":","\\:").replace("'","\\'").replace("%","\\%").replace(",","\\,")
        vf += f",drawtext=fontfile={FONT}:text='{safe}':x=(w-text_w)/2:y=110:fontsize=72:fontcolor=white:borderw=5:bordercolor=black:box=1:boxcolor=black@0.35:boxborderw=18"
    base=["ffmpeg","-y","-ss",str(start),"-i",SOURCE]
    if NARRATION_MODE in ("replace","mix"):
        voice=make_voiceover(moment,idx)
        base += ["-i",voice]
        if NARRATION_MODE == "replace":
            audio_filter=f"[1:a]apad,atrim=0:{duration}[a]"
        else:
            audio_filter=f"[0:a]volume=0.22[orig];[1:a]apad,atrim=0:{duration},volume=1[voice];[orig][voice]amix=inputs=2:duration=longest:dropout_transition=2,atrim=0:{duration}[a]"
        base += ["-filter_complex", audio_filter + f";[0:v]{vf}[v]", "-map","[v]","-map","[a]"]
    else:
        base += ["-vf",vf,"-map","0:v:0","-map","0:a?"]
    base += ["-t",str(duration),"-c:v","libx264","-preset","veryfast","-crf","21","-c:a","aac","-b:a","160k","-movflags","+faststart",out]
    run(base)
    clips.append(out)

if not clips:
    raise SystemExit("No candidate moments were found.")
concat=Path("work/concat.txt")
concat.write_text("\n".join(f"file '{Path(c).resolve()}'" for c in clips)+"\n", encoding="utf-8")
run(["ffmpeg","-y","-f","concat","-safe","0","-i",str(concat),"-c","copy","-movflags","+faststart",OUTPUT])
Path("output/analysis.json").write_text(json.dumps(ANALYSIS,indent=2),encoding="utf-8")
Path("output/scripts.txt").write_text("\n\n".join(
    f"CLIP {m.get('rank',i)}\nHOOK: {m.get('hook','')}\nSCRIPT: {m.get('script','')}\nCTA: {m.get('cta','')}\nB-ROLL SEARCH: {m.get('broll_search','')}"
    for i,m in enumerate(ANALYSIS.get("moments",[]),1)),encoding="utf-8")
Path("output/metadata.json").write_text(json.dumps({
 "source":os.environ.get("SOURCE_URL",""),"rights_confirmed":os.environ.get("RIGHTS_CONFIRMED",""),
 "niche":NICHE,"mode":"full-video-auto-analysis","font":"Anton (open-license stand-in)",
 "script_mode":ANALYSIS.get("script_mode","free transcript-based fallback"),
 "narration_mode":NARRATION_MODE,"individual_clips":clips,"montage":OUTPUT,
 "moments":ANALYSIS.get("moments",[])
},indent=2),encoding="utf-8")
