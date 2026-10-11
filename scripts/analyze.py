import json, os, re, urllib.request
from pathlib import Path

SOURCE_DURATION = float(os.environ.get("SOURCE_DURATION", "0"))
NICHE = os.environ.get("NICHE", "interesting")
MAX_CLIPS = max(1, int(os.environ.get("MAX_CLIPS", "5")))
TARGET = max(10, int(os.environ.get("TARGET_DURATION", "45")))
with open(os.environ["TRANSCRIPT_JSON"], encoding="utf-8") as f:
    transcript = json.load(f)
segments = transcript.get("segments", [])
with open("config/niches.json", encoding="utf-8") as f:
    cfg = json.load(f).get(NICHE, {})
keywords = [k.lower() for k in cfg.get("keywords", [])]
emotion = {"wow","crazy","insane","amazing","never","best","worst","secret","truth","mistake","warning","important","finally","actually","really","why","how","revealed","unbelievable","biggest"}

def score(segment):
    text = segment.get("text", "").strip()
    low = text.lower()
    words = re.findall(r"[A-Za-z0-9']+", low)
    if not words: return -999
    kw = sum(1 for k in keywords if k in low)
    emo = sum(1 for w in emotion if re.search(r"\b" + re.escape(w) + r"\b", low))
    punctuation = sum(low.count(x) for x in ["!", "?"])
    duration = max(0.5, float(segment.get("end", 0)) - float(segment.get("start", 0)))
    return kw * 5 + emo * 2 + punctuation * 1.5 + min(len(words) / duration, 4)

ranked = []
for i, seg in enumerate(segments):
    start, end = float(seg.get("start", 0)), float(seg.get("end", 0))
    if end - start >= 1 and seg.get("text", "").strip():
        ranked.append((score(seg), i, start, end, seg.get("text", "").strip()))
ranked.sort(reverse=True)
candidates = []
wanted = min(MAX_CLIPS, max(1, round(TARGET / 10)))
clip_length = max(6, min(15, TARGET / wanted))
for sc, idx, start, end, text in ranked:
    center = (start + end) / 2
    half = clip_length / 2
    a, b = max(0, center - half), min(SOURCE_DURATION, center + half)
    if b - a < 6: continue
    a, b = round(a, 2), round(b, 2)
    if any(not (b <= old_a or a >= old_b) for _, old_a, old_b, _ in candidates): continue
    candidates.append((sc, a, b, text))
    if len(candidates) >= wanted: break
candidates.sort(key=lambda x: x[1])

def make_copy(text, niche):
    clean = re.sub(r"\s+", " ", text).strip(" .!?") or "Take a look at this moment."
    words = clean.split()
    script = " ".join(words[:34]) + ("…" if len(words) > 34 else "")
    hook = {"cars":"WATCH THIS BUILD","construction":"HERE'S WHAT MATTERS","podcasts":"THIS PART IS WORTH HEARING","sports":"DON'T MISS THIS MOMENT","interesting":"LOOK CLOSER AT THIS"}.get(niche, "WATCH THIS")
    return hook, script, "Follow for more."

moments = []
for rank, (sc, start, end, text) in enumerate(candidates, 1):
    hook, script, cta = make_copy(text, NICHE)
    moments.append({"rank":rank,"score":round(sc,2),"start":start,"end":end,"text":text,
                    "hook":hook,"script":script,"cta":cta,
                    "broll_search":" ".join(re.findall(r"[A-Za-z0-9]+", text)[:5]) or cfg.get("label", NICHE)})

api_key = os.environ.get("GEMINI_API_KEY", "").strip()
script_mode = "free transcript-based fallback"
if api_key and moments:
    prompt = ("You are an editor for short vertical social videos. Return ONLY a JSON array, one object per item "
              "with keys hook, script, cta, broll_search. Hooks under 7 words. Keep scripts concise and faithful "
              "to the supplied transcript; do not invent facts. niche=" + NICHE + ". items=" +
              json.dumps([{"rank":m["rank"],"transcript":m["text"]} for m in moments]))
    try:
        payload = json.dumps({"contents":[{"parts":[{"text":prompt}]}],
                              "generationConfig":{"temperature":0.4,"responseMimeType":"application/json"}}).encode()
        req = urllib.request.Request("https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key="+api_key,
                                     data=payload,headers={"Content-Type":"application/json"},method="POST")
        with urllib.request.urlopen(req, timeout=35) as response: answer = json.loads(response.read().decode())
        generated = answer["candidates"][0]["content"]["parts"][0]["text"].strip()
        generated = re.sub(r"^\x60{3}(?:json)?\s*|\s*\x60{3}$", "", generated)
        refined = json.loads(generated)
        if isinstance(refined, list):
            for moment, copy in zip(moments, refined):
                for key in ("hook","script","cta","broll_search"):
                    if isinstance(copy.get(key), str) and copy[key].strip(): moment[key] = copy[key].strip()
            script_mode = "Gemini API (optional free tier)"
    except Exception as exc:
        print("Optional AI refinement unavailable; using free fallback:", str(exc))

out = {"source_duration":SOURCE_DURATION,"niche":NICHE,"target_duration":TARGET,
       "script_mode":script_mode,"moments":moments}
Path("work").mkdir(exist_ok=True)
Path("work/analysis.json").write_text(json.dumps(out,indent=2),encoding="utf-8")
Path("work/scripts.txt").write_text("\n\n".join(
    f"CLIP {m['rank']}\nHOOK: {m['hook']}\nSCRIPT: {m['script']}\nCTA: {m['cta']}\nB-ROLL SEARCH: {m['broll_search']}" for m in moments),encoding="utf-8")
print(json.dumps(out,indent=2))
