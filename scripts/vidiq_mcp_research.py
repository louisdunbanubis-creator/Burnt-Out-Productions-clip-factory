#!/usr/bin/env python3
"""Research Clip Factory keyword seeds through vidIQ's official MCP endpoint.

Requires VIDIQ_MCP_API_KEY as a GitHub Actions secret. Without a key, leaves
the queue untouched and exits successfully. Metrics are never fabricated.
"""
import csv
import json
import os
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

QUEUE = Path(os.environ.get("VIDIQ_QUEUE_JSON", "output/vidiq-research-queue.json"))
ENDPOINT = "https://mcp.vidiq.com/mcp"
API_KEY = os.environ.get("VIDIQ_MCP_API_KEY", "").strip()


def mcp_call(tool_name, arguments):
    """Call a tool through vidIQ's stateless Streamable HTTP MCP endpoint."""
    request_body = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
    }).encode("utf-8")
    req = urllib.request.Request(
        ENDPOINT,
        data=request_body,
        method="POST",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        # Do not print headers or credential-bearing request data.
        if exc.code == 401:
            raise RuntimeError("vidIQ rejected the API key (HTTP 401)") from None
        raise RuntimeError(f"vidIQ MCP HTTP {exc.code}") from None
    except Exception as exc:
        raise RuntimeError(f"vidIQ MCP request failed ({type(exc).__name__})") from None

    # The hosted MCP endpoint may return JSON or an SSE event containing JSON.
    candidates = []
    try:
        candidates.append(json.loads(raw))
    except json.JSONDecodeError:
        for line in raw.splitlines():
            if line.startswith("data:"):
                payload = line[5:].strip()
                if payload and payload != "[DONE]":
                    try:
                        candidates.append(json.loads(payload))
                    except json.JSONDecodeError:
                        continue
    if not candidates:
        raise RuntimeError("vidIQ MCP returned an unrecognized response")
    envelope = candidates[-1]
    if envelope.get("error"):
        raise RuntimeError("vidIQ MCP returned a protocol error")
    result = envelope.get("result", envelope)
    if result.get("isError"):
        blocks = result.get("content") or []
        message = next((b.get("text", "") for b in blocks if b.get("text")), "")
        raise RuntimeError(message[:300] or "vidIQ keyword tool failed")
    structured = result.get("structuredContent")
    if isinstance(structured, (dict, list)):
        return structured
    blocks = result.get("content") or []
    for block in blocks:
        text = block.get("text", "")
        if text:
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                continue
    return result


def rows_from(payload):
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if not isinstance(payload, dict):
        return []
    rows = []
    # Root/seed metrics may be stored in a nested object.
    for key in ("keywordData", "seedKeyword", "seed", "keywordMetrics", "metrics"):
        value = payload.get(key)
        if isinstance(value, dict) and any(k in value for k in ("keyword", "volume", "competition", "overallScore")):
            rows.append(value)
    for key in ("relatedKeywords", "keywords", "results", "data"):
        value = payload.get(key)
        if isinstance(value, list):
            rows.extend(x for x in value if isinstance(x, dict))
        elif isinstance(value, dict):
            rows.extend(rows_from(value))
    if not rows and any(k in payload for k in ("keyword", "volume", "competition", "overallScore")):
        rows.append(payload)
    # Deduplicate exact keyword rows without disturbing provider order.
    out, seen = [], set()
    for row in rows:
        name = keyword_name(row).lower()
        marker = name or json.dumps(row, sort_keys=True, default=str)
        if marker not in seen:
            out.append(row)
            seen.add(marker)
    return out


def keyword_name(row):
    for key in ("keyword", "term", "text", "query", "name"):
        if isinstance(row.get(key), str) and row[key].strip():
            return row[key].strip()
    return ""


def metric(row, *keys):
    for key in keys:
        value = row.get(key)
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, str):
            try:
                return float(value.replace(",", "").replace("%", "").strip())
            except ValueError:
                pass
    return ""


def choose_best(seed, rows):
    ranked = []
    for row in rows:
        name = keyword_name(row)
        if not name:
            continue
        volume = metric(row, "estimatedMonthlySearches", "monthlySearches", "searchVolume", "volume")
        competition = metric(row, "competition", "competitionScore")
        score = metric(row, "overallScore", "overall_score", "score")
        exact = int(name.lower() == seed.lower().strip())
        ranked.append((row, name, volume, competition, score, exact))
    if not ranked:
        return None
    measured = [item for item in ranked if item[4] != ""]
    if measured:
        return max(measured, key=lambda item: (
            item[4],
            -(item[3] if item[3] != "" else 101),
            item[5],
            item[2] if item[2] != "" else -1,
        ))
    return next((item for item in ranked if item[5]), ranked[0])


def main():
    if not API_KEY:
        print("VIDIQ_MCP_API_KEY is not set; live research skipped and metrics remain blank.")
        return 0
    if not QUEUE.exists():
        raise SystemExit(f"Keyword queue not found: {QUEUE}")
    data = json.loads(QUEUE.read_text(encoding="utf-8"))
    clips = data.get("clips", [])
    if not clips:
        print("No clips in keyword queue; nothing to research.")
        return 0

    for clip in clips:
        seed = clip.get("primary_keyword_seed") or clip.get("niche") or "YouTube Shorts"
        try:
            payload = mcp_call("vidiq_keyword_research", {
                "mode": "research",
                "keyword": seed,
                "includeRelated": True,
                "country": "US",
            })
            rows = rows_from(payload)
            best = choose_best(seed, rows)
            if not best:
                clip["research_status"] = "Needs vidIQ review"
                clip["review_notes"] = "vidIQ responded, but no usable keyword metrics were found."
                continue
            _, chosen, volume, competition, score, _ = best
            clip["primary_keyword"] = chosen
            clip["vidiq_search_volume"] = volume
            clip["vidiq_competition"] = competition
            clip["vidiq_overall_score"] = score
            clip["metrics_checked_date"] = date.today().isoformat()
            alternatives = []
            for row in rows:
                name = keyword_name(row)
                if name and name.lower() != chosen.lower() and name not in alternatives:
                    alternatives.append(name)
            clip["researched_alternative_keywords"] = alternatives[:10]
            clip["research_status"] = "Ready for human review"
            clip["review_notes"] = (
                "Live vidIQ MCP research completed. Confirm the selected phrase accurately matches "
                "the clip before publishing. Values are vidIQ estimates."
            )
            tags = clip.get("draft_tags", [])
            if chosen and chosen.lower() not in [str(tag).lower() for tag in tags]:
                tags.insert(0, chosen[:30])
            clip["draft_tags"] = tags[:15]
            print(f"vidIQ research complete for clip {clip.get('clip')}: {chosen}")
        except Exception as exc:
            clip["research_status"] = "Needs vidIQ review"
            clip["review_notes"] = f"Live vidIQ call failed; metrics left blank. {str(exc)[:180]}"
            print(f"vidIQ research failed for clip {clip.get('clip')}: {str(exc)[:180]}")

    data["vidiq_live_research"] = {
        "provider": "Official vidIQ MCP",
        "checked_date": date.today().isoformat(),
        "status": "completed_with_review" if all(
            clip.get("research_status") == "Ready for human review" for clip in clips
        ) else "partial_or_needs_review",
        "note": "Keyword metrics are estimates. Human review is required before publishing.",
    }
    QUEUE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
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
                    row[key] = " | ".join(str(value) for value in row[key])
            writer.writerow({key: row.get(key, "") for key in fields})
    print(f"Updated vidIQ results in {QUEUE} and {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
