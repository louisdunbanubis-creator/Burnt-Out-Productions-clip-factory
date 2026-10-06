import json, os, re
from pathlib import Path

SOURCE_DURATION=float(os.environ.get("SOURCE_DURATION","0"))
NICHE=os.environ.get("NICHE","interesting")
MAX_CLIPS=int(os.environ.get("MAX_CLIPS","5"))
TARGET=int(os.environ.get("TARGET_DURATION","45"))

with open(os.environ["TRANSCRIPT_JSON"],encoding="utf-8") as f:
    data=json.load(f)

segments=data.get("segments",[])
cfg=json.load(open("config/niches.json",encoding="utf-8")).get(NICHE,{})
keywords=[k.lower() for k in cfg.get("keywords",[])]

emotion={"wow","crazy","insane","amazing","never","best","worst","secret","truth","mistake","warning","important","finally","actually","really","why","how"}

def score(s):
    text=s.get("text","").strip()
    low=text.lower()
    words=re.findall(r"[A-Za-z0-9']+",low)
    if not words: return -999
    kw=sum(1 for k in keywords if k in low)
    emo=sum(1 for w in emotion if re.search(r"\\b"+re.escape(w)+r"\\b",low))
    punctuation=sum(low.count(x) for x in ["!","?"])
    density=len(words)/max(0.5,float(s.get("end",0))-float(s.get("start",0)))
    return kw*5 + emo*2 + punctuation*1.5 + min(density,4)

ranked=[]
for i,s in enumerate(segments):
    st=float(s.get("start",0)); en=float(s.get("end",st))
    if en-st < 1: continue
    ranked.append((score(s),i,st,en,s.get("text","").strip()))
ranked.sort(reverse=True)

candidates=[]
for sc,i,st,en,text in ranked:
    # Build a natural short moment around the strongest transcript segment.
    center=(st+en)/2
    start=max(0,center-6)
    end=min(SOURCE_DURATION,center+7)
    # Avoid very short tails and keep each moment under 15 seconds.
    if end-start < 6: continue
    start=round(start,2); end=round(end,2)
    if any(not (end <= a or start >= b) for _,a,b,_,_ in candidates):
        continue
    candidates.append((sc,start,end,text))
    if len(candidates)>=MAX_CLIPS: break

candidates.sort(key=lambda x:x[1])
total=sum(b-a for _,a,b,_ in candidates)
# If the selected moments are too short, extend them while preserving their centers.
if total < min(TARGET, MAX_CLIPS*8):
    expanded=[]
    for sc,a,b,t in candidates:
        c=(a+b)/2
        na=max(0,c-8); nb=min(SOURCE_DURATION,c+8)
        expanded.append((sc,round(na,2),round(nb,2),t))
    candidates=expanded

Path("work").mkdir(exist_ok=True)
out={"source_duration":SOURCE_DURATION,"niche":NICHE,"target_duration":TARGET,
     "moments":[{"score":round(sc,2),"start":a,"end":b,"text":t} for sc,a,b,t in candidates]}
Path("work/analysis.json").write_text(json.dumps(out,indent=2),encoding="utf-8")
print(json.dumps(out,indent=2))
