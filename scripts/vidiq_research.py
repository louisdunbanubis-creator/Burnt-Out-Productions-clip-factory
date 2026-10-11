#!/usr/bin/env python3
"""Create a per-clip vidIQ keyword research queue without inventing metrics."""
import csv
import json
import os
import re
from datetime import date
from pathlib import Path

ANALYSIS_FILE = Path(os.environ.get("ANALYSIS_FILE", "work/analysis.json"))
OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "output"))
SOURCE_URL = os.environ.get("SOURCE_URL", "")
NICHE = os.environ.get("NICHE", "interesting")

STOP = set("""
a an and are as at be been but by can did do does for from had has have he her here hers him his
how i if in into is it its just me my of on or our ours she so than that the their them then there
these they this those to too up us was we were what when where which who why will with you your
you're it's don't can't isn't wasn't that's really very like get got make made one thing things
""".split())

def clean(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()

def phrases(text):
    words = re.findall(r"[a-z0-9][a-z0-9'-]*", clean(text).lower())
    out = []
    # Specific 2-4 word phrases from the clip's own transcript.
    for size in (3, 2, 4):
        for i in range(max(0, len(words) - size + 1)):
            chunk = words[i:i + size]
            if sum(w not in STOP for w in chunk) < 2:
                continue
            phrase = " ".join(chunk).strip("-'")
            if len(phrase) >= 7 and phrase not in out:
                out.append(phrase)
    # Strong individual topic words, preserving transcript relevance.
    for word in words:
        if len(word) >= 4 and word not in STOP and word not in out:
            out.append(word)
    return out

def main():
    data = json.loads(ANALYSIS_FILE.read_text(encoding="utf-8"))
    cfg_path = Path("config/niches.json")
    cfg = json.loads(cfg_path.read_text(encoding="utf-8")).get(NICHE, {}) if cfg_path.exists() else {}
    niche_label = cfg.get("label", NICHE)
    niche_terms = [clean(x).lower() for x in cfg.get("keywords", []) if clean(x)]
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    records = []
    for idx, moment in enumerate(data.get("moments", []), 1):
        transcript = clean(moment.get("text", ""))
        title_hook = clean(moment.get("hook", ""))
        # Candidate list is only a starting point for human verification in vidIQ.
        candidates = []
        for term in phrases(transcript) + [x for x in niche_terms if x in transcript.lower()] + [niche_label.lower()]:
            term = clean(term).strip(" .,!?:;")
            if term and term not in candidates and len(term) <= 70:
                candidates.append(term)
        candidates = candidates[:12]
        primary_seed = candidates[0] if candidates else niche_label.lower()
        title = clean(f"{title_hook}: {transcript}") if title_hook else transcript
        title = title[:95].rstrip(" ,.!?:;-")
        description = clean(
            f"{transcript} This clip is about {niche_label.lower()}. "
            f"Keyword research pending: verify the best relevant phrase in vidIQ before publishing."
        )
        tags = []
        for tag in [*candidates[:8], *niche_terms, NICHE.replace("_", " ").lower()]:
            tag = clean(tag).strip(" ,")
            if tag and tag.lower() not in [t.lower() for t in tags] and len(tag) <= 30:
                tags.append(tag)
        records.append({
            "clip": idx,
            "start_seconds": moment.get("start", ""),
            "end_seconds": moment.get("end", ""),
            "source_url": SOURCE_URL,
            "niche": niche_label,
            "primary_keyword_seed": primary_seed,
            "candidate_keywords": candidates,
            "vidiq_search_volume": "",
            "vidiq_competition": "",
            "vidiq_overall_score": "",
            "metrics_checked_date": "",
            "draft_title": title,
            "draft_description": description,
            "draft_tags": tags,
            "research_status": "Needs vidIQ review",
            "review_notes": "Search volume and competition intentionally blank until checked in vidIQ."
        })
    (OUTPUT_DIR / "vidiq-research-queue.json").write_text(
        json.dumps({"instructions": [
            "Open vidIQ Research > Keywords (or the vidIQ app in ChatGPT) for each clip.",
            "Search the candidate phrases and record the displayed search volume, competition, and overall score if available.",
            "Choose a relevant high-demand, lower-competition phrase; do not choose unrelated terms for volume alone.",
            "Fill the metric fields and date, revise title/description/tags, then mark Ready for review.",
            "vidIQ search volume is an estimate. No metrics in this file have been fabricated."
        ], "clips": records}, indent=2, ensure_ascii=False), encoding="utf-8")
    with (OUTPUT_DIR / "vidiq-research-queue.csv").open("w", newline="", encoding="utf-8-sig") as f:
        fields = ["clip","start_seconds","end_seconds","source_url","niche","primary_keyword_seed",
                  "candidate_keywords","vidiq_search_volume","vidiq_competition","vidiq_overall_score",
                  "metrics_checked_date","draft_title","draft_description","draft_tags","research_status","review_notes"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for record in records:
            row = dict(record)
            for key in ("candidate_keywords", "draft_tags"):
                row[key] = " | ".join(row[key])
            writer.writerow(row)
    print(f"Wrote vidIQ keyword research queue for {len(records)} clips to {OUTPUT_DIR}/vidiq-research-queue.csv and .json")

if __name__ == "__main__":
    main()
