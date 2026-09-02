#!/usr/bin/env python3
"""Probe 1: process table grouped by parent session with working-set totals.

Catalog evidence: live OS table, parent-session attribution, RSS sums.
Control: reported set excludes this probe (pid, argv, starttime).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import census as C  # noqa: E402

REPO = HERE.parents[3]
ART = REPO / "command-center/audit/AUD-0061-mcp-process-multiplication.json"
SENTINEL = (
    "SUCCESS:AUD-0061 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0061-probe1 {msg}")
    return 1


def main() -> int:
    ctl = C.self_match_control()
    if not ctl["pass"]:
        return fail(f"self-match control did not discriminate {json.dumps(ctl)}")
    if not ctl["fired_on_bad_state"] or not ctl["silent_on_good_state"]:
        return fail("both-states self-match control incomplete")

    live = C.live_census()
    if live["self_pid_in_reported_set"]:
        return fail("live census included probe pid")
    if live["same_starttime_in_reported_set"]:
        return fail("live census included a process with probe starttime")
    if live["probe_pid"] != os.getpid():
        return fail("probe_pid mismatch")
    for group in live["by_parent_session"]:
        summed = sum(c["rss_bytes"] for c in group["children"])
        if summed != group["rss_bytes_mcp"]:
            return fail(f"working-set total mismatch {group['session_key']}")
        if group["mcp_count"] != len(group["children"]):
            return fail(f"mcp_count mismatch {group['session_key']}")

    claim = C.catalog_claim()
    if claim["arithmetic_consistent"]:
        return fail("catalog 23*65==2037 is false; detector must not bless it")
    if claim["arithmetic_product"] != 1495:
        return fail(f"product {claim['arithmetic_product']}")
    if claim["claimed_processes"] != 2037:
        return fail("catalog claimed_processes drifted")

    model = C.stdio_multiplication_model(23, 65, 12 * 1024 * 1024)
    if model["stdio_process_count"] != 1495:
        return fail("model used the catalog's false product")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        return fail("sentinel-absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")
    if doc.get("unit_id") != "AUD-0061":
        return fail(f"unit_id={doc.get('unit_id')}")

    headline = (doc.get("report") or {}).get("headline") or {}
    if headline.get("catalog_arithmetic_product") != 1495:
        return fail("artifact repeated the false catalog product")
    if headline.get("catalog_claimed_processes") != 2037:
        return fail("artifact dropped the recorded claim")
    if headline.get("catalog_arithmetic_consistent") is not False:
        return fail("artifact did not record arithmetic inconsistency")
    if not isinstance(headline.get("live_mcp_process_count"), int):
        return fail("artifact missing live mcp count")
    groups = ((doc.get("report") or {}).get("live_census") or {}).get("by_parent_session")
    if not isinstance(groups, list):
        return fail("artifact missing by_parent_session grouping")
    named = doc.get("named_probes") or []
    if len(named) < 2:
        return fail("artifact named_probes missing")
    raw1 = " ".join(str(p.get("raw_output") or "") for p in named)
    if "by_parent_session" not in raw1 and "rss_bytes_mcp" not in raw1:
        return fail("probe1 verbatim output not recorded in artifact")

    out = {
        "probe": "probe1-session-working-set",
        "unit_id": "AUD-0061",
        "pass": True,
        "live_mcp_count": live["mcp_count"],
        "live_session_count": live["session_count"],
        "rss_bytes_mcp_total": live["rss_bytes_mcp_total"],
        "groups": len(live["by_parent_session"]),
        "self_excluded": True,
        "same_starttime_excluded": True,
        "catalog_product": 1495,
        "catalog_claimed": 2037,
        "control": {
            "fired_on_bad_state": ctl["fired_on_bad_state"],
            "silent_on_good_state": ctl["silent_on_good_state"],
            "mention_counted_by_naive": ctl["mention_counted_by_naive"],
            "mention_counted_by_token": ctl["mention_counted_by_token"],
        },
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"mcp={live['mcp_count']} sessions={live['session_count']} "
        f"rss_mcp={live['rss_bytes_mcp_total']} groups={len(live['by_parent_session'])} "
        f"catalog_23x65=1495_not_2037"
    )
    print("SUCCESS:AUD-0061-probe1 session working-set census and self-match control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
