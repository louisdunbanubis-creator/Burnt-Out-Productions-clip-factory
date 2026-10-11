#!/usr/bin/env python3
"""Research Clip Factory keyword seeds through the official vidIQ MCP server.

Requires VIDIQ_MCP_API_KEY. If absent, leaves the existing queue untouched so
the workflow remains usable without credentials. Metrics are only written from
actual vidIQ responses; failed calls are marked for review, never fabricated.
"""
import asyncio
import json
import os
from datetime import date
from pathlib import Path

QUEUE = Path(os.environ.get("VIDIQ_QUEUE_JSON", "output/vidiq-research-queue.json"))
ENDPOINT = "https://mcp.vidiq.com/mcp"
API_KEY = os.environ.get("VIDIQ_MCP_API_KEY", "").strip()


def text_from_result(result):
    chunks = []
    for item in getattr(result, "content", []) or []:
        value = getattr(item, "text", None)
        if value:
            chunks.append(value)
    return "\n".join(chunks)


def parse_payload(raw):
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Some MCP tools wrap JSON in explanatory text or fenced blocks.
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(raw[start:end + 1])
            except json.JSONDecodeError:
                pass
    return {}


def rows_from(payload):
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("relatedKeywords", "keywords", "results", "data"):
        value = payload.get(key)
        if isinstance(value, list):
            return [x for x in value if isinstance(x, dict)]
        if isinstance(value, dict):
            nested = rows_from(value)
            if nested:
                return nested
    # Some responses return the seed metrics at the top level.
    if any(k in payload for k in ("keyword", "volume", "competition", "overallScore")):
        return [payload]
    return []


def num(row, *keys):
    for key in keys:
        value = row.get(key)
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, str):
            try:
                return float(value.replace(",", "").replace("%", "").strip())
            except ValueError:
                continue
    return ""


def keyword_name(row):
    for key in ("keyword", "term", "text", "query"):
        if isinstance(row.get(key), str) and row[key].strip():
            return row[key].strip()
    return ""


async def research_one(session, seed):
    result = await session.call_tool(
        "vidiq_keyword_research",
        arguments={
            "mode": "research",
            "keyword": seed,
            "includeRelated": True,
            "country": "US",
        },
    )
    if getattr(result, "isError", False):
        raise RuntimeError(text_from_result(result) or "vidIQ returned a tool error")
    payload = parse_payload(text_from_result(result))
    rows = rows_from(payload)
    # Include the root metrics if returned separately.
    root = payload.get("keywordData") if isinstance(payload, dict) else None
    if isinstance(root, dict):
        rows.insert(0, root)
    return payload, rows


def choose_best(seed, rows):
    seed_norm = seed.lower().strip()
    ranked = []
    for row in rows:
        name = keyword_name(row)
        if not name:
            continue
        volume = num(row, "estimatedMonthlySearches", "monthlySearches", "searchVolume", "volume")
        competition = num(row, "competition", "competitionScore")
        score = num(row, "overallScore", "overall_score", "score")
        # The overall score is vidIQ's opportunity metric. Use it when present;
        # otherwise preserve the returned row order instead of inventing a score.
        relevance = 1 if name.lower() == seed_norm else 0
        ranked.append((row, name, volume, competition, score, relevance))
    if not ranked:
        return None
    measured = [x for x in ranked if x[4] != ""]
    if measured:
        # Best score first; use lower competition as a tie-breaker, then demand.
        return max(measured, key=lambda x: (x[4], -(x[3] if x[3] != "" else 101), x[5], x[2] if x[2] != "" else -1))
    return next((x for x in ranked if x[1].lower() == seed_norm), ranked[0])


async def main():
    if not API_KEY:
        print("VIDIQ_MCP_API_KEY is not set; skipped live vidIQ calls. Queue remains marked for research.")
        return 0
    if not QUEUE.exists():
        raise SystemExit(f"Keyword queue not found: {QUEUE}")
    try:
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client
    except ImportError as exc:
        raise SystemExit("Python MCP SDK missing. Install with: pip install mcp") from exc

    data = json.loads(QUEUE.read_text(encoding="utf-8"))
    clips = data.get("clips", [])
    if not clips:
        print("No clips in keyword queue; nothing to research.")
        return 0

    # The official vidIQ MCP server uses the standard MCP protocol. The API key
    # is passed as a bearer credential and never written to artifacts or logs.
    async with streamablehttp_client(
        ENDPOINT,
        headers={"Authorization": f"Bearer {API_KEY}"},
    ) as (read_stream, write_stream, _get_session_id):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            for clip in clips:
                seed = clip.get("primary_keyword_seed") or clip.get("niche") or "YouTube Shorts"
                try:
                    payload, rows = await research_one(session, seed)
                    best = choose_best(seed, rows)
                    if not best:
                        clip["research_status"] = "Needs vidIQ review"
                        clip["review_notes"] = "vidIQ responded, but no usable keyword metrics were found."
                        continue
                    row, chosen, volume, competition, score, _ = best
                    clip["primary_keyword"] = chosen
                    clip["vidiq_search_volume"] = volume
                    clip["vidiq_competition"] = competition
                    clip["vidiq_overall_score"] = score
                    clip["metrics_checked_date"] = date.today().isoformat()
                    alternatives = []
                    for candidate in rows:
                        name = keyword_name(candidate)
                        if name and name.lower() != chosen.lower() and name not in alternatives:
                            alternatives.append(name)
                    clip["researched_alternative_keywords"] = alternatives[:10]
                    clip["research_status"] = "Ready for human review"
                    clip["review_notes"] = (
                        "Live vidIQ MCP research completed. Confirm the chosen keyword accurately matches "
                        "the clip before publishing. Values are vidIQ estimates."
                    )
                    clip["vidiq_response_summary"] = {
                        "keyword": chosen,
                        "volume": volume,
                        "competition": competition,
                        "overall_score": score,
                    }
                    # Keep metadata suggestions relevant; don't replace the title automatically.
                    if chosen and chosen.lower() not in [str(t).lower() for t in clip.get("draft_tags", [])]:
                        tags = clip.get("draft_tags", [])
                        tags.insert(0, chosen[:30])
                        clip["draft_tags"] = tags[:15]
                    print(f"vidIQ research complete for clip {clip.get('clip')}: {chosen}")
                except Exception as exc:
                    clip["research_status"] = "Needs vidIQ review"
                    clip["review_notes"] = f"Live vidIQ call failed; metrics left blank. Error: {type(exc).__name__}"
                    print(f"vidIQ research failed for clip {clip.get('clip')}: {type(exc).__name__}")

    data["vidiq_live_research"] = {
        "provider": "Official vidIQ MCP",
        "checked_date": date.today().isoformat(),
        "status": "completed_with_review" if all(c.get("research_status") == "Ready for human review" for c in clips) else "partial_or_needs_review",
        "note": "Keyword metrics are estimates. Human review is required before publishing.",
    }
    QUEUE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    # Keep CSV synchronized with the JSON record.
    import csv
    csv_path = QUEUE.with_suffix(".csv")
    fields = [
        "clip", "start_seconds", "end_seconds", "source_url", "niche",
        "primary_keyword_seed", "primary_keyword", "candidate_keywords",
        "researched_alternative_keywords", "vidiq_search_volume", "vidiq_competition",
        "vidiq_overall_score", "metrics_checked_date", "draft_title", "draft_description",
        "draft_tags", "research_status", "review_notes",
    ]
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for clip in clips:
            row = dict(clip)
            for key in ("candidate_keywords", "researched_alternative_keywords", "draft_tags"):
                if isinstance(row.get(key), list):
                    row[key] = " | ".join(str(x) for x in row[key])
            writer.writerow({key: row.get(key, "") for key in fields})
    print(f"Updated live vidIQ research results in {QUEUE} and {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
