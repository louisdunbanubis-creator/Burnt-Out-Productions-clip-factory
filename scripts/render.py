import json, os, subprocess, shlex
from pathlib import Path

SOURCE=os.environ["SOURCE_FILE"]
OUTPUT=os.environ.get("OUTPUT_FILE","output/best_of.mp4")
NICHE=os.environ.get("NICHE","interesting")
HOOK=os.environ.get("HOOK","").strip()
FONT=os.environ.get("FONT_FILE","/usr/share/fonts/truetype/anton/Anton-Regular.ttf")
ANALYSIS=json.load(open(os.environ.get("ANALYSIS_FILE","work/analysis.json"),encoding="utf-8"))
TRANSCRIPT=json.load(open(os.environ.get("TRANSCRIPT_JSON","work/transcript.json"),encoding="utf-8"))

Path("work/rendered").mkdir(parents=True,exist_ok=True)

def run(cmd):
    print("$"," ".join(shlex.quote(str(x)) for x in cmd),flush=True)
    subprocess.run(cmd,check=True)

def ass_escape(s):
    return s.replace("\\","\\\\").replace("{","\\{").replace("}","\\}").replace("\n"," ")

def ass_time(sec):
    h=int(sec//3600); m=int((sec%3600)//60); s=sec%60
    return f"{h}:{m:02d}:{s:05.2f}"

def write_ass(path,start,end):
    rows=["[Script Info]","ScriptType: v4.00+","PlayResX: 1080","PlayResY: 1920",
          "[V4+ Styles]","Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Alignment,MarginL,MarginR,MarginV,BorderStyle,Outline,Shadow",
          "Style: Brand,Anton,62,&H00FFFFFF,&H00FFFFFF,&H00000000,&H88000000,0,0,2,70,70,190,1,4,0",
          "[Events]","Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text"]
    for seg in TRANSCRIPT.get("segments",[]):
        a=float(seg.get("start",0)); b=float(seg.get("end",0))
        if b<=start or a>=end: continue
        a=max(a,start)-start; b=min(b,end)-start
        txt=ass_escape(seg.get("text","").strip())
        if txt: rows.append(f"Dialogue: 0,{ass_time(a)},{ass_time(b)},Brand,,0,0,0,,{txt}")
    Path(path).write_text("\n".join(rows)+"\n",encoding="utf-8")

clips=[]
for idx,m in enumerate(ANALYSIS["moments"],1):
    a=float(m["start"]); b=float(m["end"]); dur=max(1,b-a)
    ass=f"work/rendered/captions_{idx}.ass"
    write_ass(ass,a,b)
    out=f"work/rendered/moment_{idx}.mp4"
    vf=f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,subtitles={ass}"
    if HOOK:
        safe=HOOK.replace("\\","\\\\").replace(":","\\:").replace("'","\\'").replace("%","\\%")
        vf += f",drawtext=fontfile={FONT}:text='{safe}':x=(w-text_w)/2:y=110:fontsize=72:fontcolor=white:borderw=5:bordercolor=black:box=1:boxcolor=black@0.35:boxborderw=18"
    run(["ffmpeg","-y","-ss",str(a),"-i",SOURCE,"-t",str(dur),"-vf",vf,
         "-map","0:v:0","-map","0:a?","-c:v","libx264","-preset","veryfast","-crf","21",
         "-c:a","aac","-b:a","160k","-movflags","+faststart",out])
    clips.append(out)

if not clips: raise SystemExit("No candidate moments were found.")
concat=Path("work/concat.txt")
concat.write_text("\n".join(f"file '{Path(c).resolve()}'" for c in clips)+"\n",encoding="utf-8")
Path(OUTPUT).parent.mkdir(parents=True,exist_ok=True)
run(["ffmpeg","-y","-f","concat","-safe","0","-i",str(concat),"-c","copy","-movflags","+faststart",OUTPUT])
Path("output/analysis.json").write_text(json.dumps(ANALYSIS,indent=2),encoding="utf-8")
Path("output/metadata.json").write_text(json.dumps({
 "source":os.environ.get("SOURCE_URL",""),"rights_confirmed":os.environ.get("RIGHTS_CONFIRMED",""),
 "niche":NICHE,"mode":"full-video-auto-analysis","font":"Anton (brand display style)",
 "moments":ANALYSIS["moments"],"output":OUTPUT
},indent=2),encoding="utf-8")
