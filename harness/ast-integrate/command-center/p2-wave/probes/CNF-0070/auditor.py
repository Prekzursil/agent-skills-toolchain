#!/usr/bin/env python3
"""Archival corroboration of live-mismatch citations.

Verdicts are not merged:
  was-true-then-changed — a snapshot captured on or before the citation date
                          contains the quote; the live page does not.
  never-supported       — at least one timely snapshot exists and none of them
                          contain the quote (later snapshots are ignored).
  no-snapshot-available — no snapshot captured on or before the citation date.
"""
from __future__ import annotations

import difflib
import json
from collections import Counter
from pathlib import Path

from archive import (
    capture_on_or_before,
    live_page,
    locate_quote,
    never_execute_archived,
    scan_untrusted,
    snapshots_for,
)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIX = HERE / "fixtures"
UPSTREAM = REPO / "command-center/confirmation/CNF-0062-citation-liveness.json"
FIXTURE_INV = FIX / "failed-citations.json"

WAS_TRUE = "was-true-then-changed"
NEVER = "never-supported"
NO_SNAP = "no-snapshot-available"
LIVE_MATCH = "live-match"


def _diff(live_body: str, snap_body: str) -> str:
    lines = list(
        difflib.unified_diff(
            snap_body.splitlines(),
            live_body.splitlines(),
            fromfile="snapshot",
            tofile="live",
            lineterm="",
            n=2,
        )
    )
    text = "\n".join(lines)
    if len(text) > 4000:
        return text[:4000] + "\n...[truncated]..."
    return text


def load_failed_citations() -> tuple[list[dict], dict]:
    meta = {
        "upstream_output_path": "command-center/confirmation/CNF-0062-citation-liveness.json",
        "upstream_present": UPSTREAM.is_file() and UPSTREAM.stat().st_size > 0,
        "input_used": None,
        "note": "",
    }
    if meta["upstream_present"]:
        doc = json.loads(UPSTREAM.read_text(encoding="utf-8"))
        rows = []
        for c in doc.get("citations") or []:
            if not isinstance(c, dict):
                continue
            verdict = str(c.get("verdict") or "")
            live_ok = bool((c.get("live") or {}).get("quote_present"))
            if verdict in {LIVE_MATCH, "ok", "reachable-and-matched"} or live_ok:
                continue
            if c.get("url") and c.get("quoted_span") and c.get("citation_date"):
                rows.append(c)
        if rows:
            meta["input_used"] = meta["upstream_output_path"]
            meta["note"] = "Failed citations taken from CNF-0062 artifact."
            return rows, meta
    inv = json.loads(FIXTURE_INV.read_text(encoding="utf-8"))
    meta["input_used"] = "command-center/p2-wave/probes/CNF-0070/fixtures/failed-citations.json"
    meta["note"] = inv.get("note") or "CNF-0062 absent; fixture inventory used."
    return list(inv.get("citations") or []), meta


def classify(citation: dict, *, accept_late: bool = False) -> dict:
    url = str(citation["url"])
    quote = str(citation["quoted_span"])
    cited = str(citation["citation_date"])
    live = live_page(url)
    live_hit = locate_quote(live["body"], quote)
    live_untrusted = scan_untrusted(live["body"]) if live["body"] else []

    considered = []
    accepted = []
    rejected = []
    untrusted: list[dict] = list(live_untrusted)
    for snap in snapshots_for(url):
        never_execute_archived(snap["body"])
        hit = locate_quote(snap["body"], quote)
        body_untrusted = scan_untrusted(snap["body"])
        untrusted.extend(body_untrusted)
        timely = capture_on_or_before(snap["capture_timestamp"], cited)
        rec = {
            "snapshot_url": snap["snapshot_url"],
            "capture_timestamp": snap["capture_timestamp"],
            "body_path": snap["body_path"],
            "sha256": snap["sha256"],
            "quote_located": hit["found"],
            "quote_offset": hit["offset"],
            "located_quote": hit["located_quote"],
            "untrusted_instruction_count": len(body_untrusted),
            "accepted": False,
            "rejection_reason": None,
        }
        if timely or accept_late:
            rec["accepted"] = True
            if not timely and accept_late:
                rec["rejection_reason"] = None
                rec["naive_late_accepted"] = True
            accepted.append(rec)
        else:
            rec["rejection_reason"] = "capture-after-citation-date"
            rejected.append(rec)
        considered.append(rec)

    supporting = [a for a in accepted if a["quote_located"]]
    supporting.sort(key=lambda r: r["capture_timestamp"])
    corroboration = None
    snap_body_for_diff = ""
    if supporting:
        chosen = supporting[-1]
        corroboration = {
            "snapshot_url": chosen["snapshot_url"],
            "capture_timestamp": chosen["capture_timestamp"],
            "located_quote": chosen["located_quote"],
            "quote_offset": chosen["quote_offset"],
            "body_path": chosen["body_path"],
            "sha256": chosen["sha256"],
        }
        for snap in snapshots_for(url):
            if snap["capture_timestamp"] == chosen["capture_timestamp"]:
                snap_body_for_diff = snap["body"]
                break
        if live_hit["found"]:
            verdict = LIVE_MATCH
            failure_class = None
        else:
            verdict = WAS_TRUE
            failure_class = "source-changed"
    elif not accepted:
        verdict = NO_SNAP
        failure_class = "no-snapshot-available"
    else:
        verdict = NEVER
        failure_class = "never-supported"
        latest = max(accepted, key=lambda r: r["capture_timestamp"])
        for snap in snapshots_for(url):
            if snap["capture_timestamp"] == latest["capture_timestamp"]:
                snap_body_for_diff = snap["body"]
                break

    diff = None
    if snap_body_for_diff or live["body"]:
        diff = _diff(live["body"], snap_body_for_diff) if snap_body_for_diff else None

    return {
        "id": citation.get("id"),
        "url": url,
        "citation_date": cited,
        "quoted_span": quote,
        "claim": citation.get("claim"),
        "live_failure": citation.get("live_failure"),
        "live": {
            "reachable": live["reachable"],
            "http_status": live["http_status"],
            "quote_present": live_hit["found"],
            "quote_offset": live_hit["offset"],
            "body_path": live["body_path"],
            "sha256": live["sha256"],
        },
        "snapshots_considered": considered,
        "rejected_snapshots": rejected,
        "archived_corroboration": corroboration,
        "live_versus_snapshot_diff": diff,
        "untrusted_instructions_recorded": untrusted,
        "archived_content_executed": False,
        "verdict": verdict,
        "failure_class": failure_class,
    }


def audit_all(*, accept_late: bool = False) -> dict:
    citations, meta = load_failed_citations()
    rows = [classify(c, accept_late=accept_late) for c in citations]
    counts = Counter(r["verdict"] for r in rows)
    timely_ok = True
    for r in rows:
        corr = r.get("archived_corroboration")
        if not corr:
            continue
        if not capture_on_or_before(corr["capture_timestamp"], r["citation_date"]):
            timely_ok = False
            break
    return {
        "upstream": meta,
        "citations": rows,
        "summary": {
            "citation_count": len(rows),
            "verdict_counts": dict(counts),
            "every_archived_corroboration_timely": timely_ok,
            "was_true_then_changed_count": counts.get(WAS_TRUE, 0),
            "never_supported_count": counts.get(NEVER, 0),
            "no_snapshot_available_count": counts.get(NO_SNAP, 0),
            "verdicts_are_distinct": WAS_TRUE != NEVER,
        },
    }


def by_id(result: dict) -> dict[str, dict]:
    return {str(r["id"]): r for r in result.get("citations") or []}
