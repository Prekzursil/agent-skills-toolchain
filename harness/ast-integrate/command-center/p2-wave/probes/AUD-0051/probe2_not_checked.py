#!/usr/bin/env python3
"""Probe 2: projects with no thresholds file are NOT-CHECKED, never a pass.

Folding absence into a silent pass is the banned outcome.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import census as C  # noqa: E402
from coverage_extract import canned_control, extract_coverage  # noqa: E402

UNIT = "AUD-0051"
ART = C.REPO / C.OUT_REL
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def looks_like_number(value: object) -> bool:
    text = str(value or "")
    if text in {"", "NOT-CHECKED", "None"}:
        return False
    return text.endswith("%") or text.replace(".", "", 1).isdigit()


def main() -> int:
    canned = canned_control()
    live = C.discover_live()
    ungated = [p for p in live if not p.get("has_thresholds_file")]
    gated = [p for p in live if p.get("has_thresholds_file")]
    folded = [p["path"] for p in ungated if looks_like_number(p.get("coverage"))]
    missing_flag = [
        p["path"]
        for p in ungated
        if p.get("coverage") != "NOT-CHECKED"
    ]

    # Explicit fixture with no thresholds file must not become a pass.
    plain = C.inspect_project(C.FIXTURE_PLAIN)
    fixture_ok = (
        plain["has_thresholds_file"] is False
        and plain["coverage"] == "NOT-CHECKED"
        and not looks_like_number(plain["coverage"])
    )
    good_val, good_why = extract_coverage(canned["good_state_input"])
    extractor_not_stuck = good_val != "NOT-CHECKED"

    ok = (
        canned["pass"]
        and fixture_ok
        and extractor_not_stuck
        and not folded
        and not missing_flag
        and len(live) >= 1
    )
    payload = {
        "pass": bool(ok),
        "probe": "probe2-not-checked",
        "unit_id": UNIT,
        "reviewer_id": "AUD-0051-probe2-not-checked",
        "live_projects": len(live),
        "live_gated": len(gated),
        "live_ungated": len(ungated),
        "ungated_all_not_checked": not missing_flag,
        "folded_into_number": folded,
        "fixture_plain_not_checked": fixture_ok,
        "extractor_good_state": [good_val, good_why],
        "paths": [p["path"] for p in live],
    }
    print(json.dumps(payload, sort_keys=True))

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail(f"artifact absent {ART}")
    text = ART.read_text(encoding="utf-8")
    if C.SENTINEL not in text:
        return fail("sentinel absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in NOT_DELIVERING:
        return fail(f"self-declared {doc.get('state')}")
    headline = doc.get("headline") or {}
    if headline.get("ungated_not_checked") != len(ungated):
        return fail(
            f"headline ungated_not_checked {headline.get('ungated_not_checked')} "
            f"!= {len(ungated)}"
        )
    if headline.get("gated") != len(gated):
        return fail(f"headline gated {headline.get('gated')} != {len(gated)}")
    if headline.get("projects") != len(live):
        return fail(f"headline projects {headline.get('projects')} != {len(live)}")
    projects = (doc.get("report") or {}).get("projects") or doc.get("projects") or []
    art_folded = [
        p.get("path")
        for p in projects
        if isinstance(p, dict)
        and not p.get("has_thresholds_file")
        and looks_like_number(p.get("coverage"))
    ]
    if art_folded:
        return fail(f"artifact folded absence into a number: {art_folded[:8]}")
    if headline.get("projects_with_a_measured_coverage_number") not in (0, None):
        if headline.get("projects_with_a_measured_coverage_number") != 0:
            return fail("artifact claims a measured coverage number")
    if not ok:
        return fail(
            f"gated={len(gated)} folded={folded} missing={missing_flag} "
            f"fixture_ok={fixture_ok}"
        )
    print(
        "SUCCESS:AUD-0051-probe2 every ungated project is NOT-CHECKED; "
        "absence is not a silent pass"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
