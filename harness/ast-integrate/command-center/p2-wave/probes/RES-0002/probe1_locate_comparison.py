#!/usr/bin/env python3
"""Probe 1: locate the HTTP-200-to-FAILED comparison, or explicit REFUTED.

Signal 1: regex over hook-shaped sources.
Signal 2: ast.walk Compare/Return (not a regex re-run).
Both-states: inverted fixtures fire; correct/noop stay silent.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from constants import OUTPUT_REL, REPO, SENTINEL, UNIT_ID  # noqa: E402
from measure import measure  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT_ID}-probe1 {msg}")
    return 1


def main() -> int:
    art = REPO / OUTPUT_REL
    if not art.is_file() or art.stat().st_size <= 0:
        return fail("artifact missing")
    text = art.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"unparseable:{type(exc).__name__}")
    if doc.get("unit_id") != UNIT_ID:
        return fail(f"unit_id {doc.get('unit_id')}")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    if SENTINEL not in text:
        return fail("sentinel-absent")

    live = measure()
    scan = live["scanner_both_states"]
    if not scan["passed"]:
        return fail("scanner both-states did not discriminate")
    if not scan["fires_on_broken"] or not scan["silent_on_good"]:
        return fail("scanner control split failed")

    rec = doc.get("http_200_to_failed_comparison") or {}
    live_cmp = live["comparison"]
    if rec.get("live_verdict") != live_cmp.get("live_verdict"):
        return fail("live comparison verdict drifted")
    if live_cmp.get("live_verdict") == "REFUTED":
        if "REFUTED" not in text:
            return fail("explicit REFUTED missing from artifact")
        if rec.get("live_exists") is True:
            return fail("artifact claimed a live line while scan is REFUTED")
    else:
        if not rec.get("live_file_line"):
            return fail("FOUND without file:line")

    fixture = rec.get("fixture_eq_200") or {}
    if not fixture.get("file_line"):
        return fail("fixture eq-200 file:line missing")
    if str(fixture.get("line")) not in str(fixture.get("file_line")):
        return fail("fixture file:line mismatch")

    regex_ok = all(
        scan["broken_regex_and_ast"][name]["regex"]
        and scan["broken_regex_and_ast"][name]["ast"]
        for name in ("inverted_status_as_exit", "inverted_eq_200")
    )
    if not regex_ok:
        return fail("both signals did not fire on inverted fixtures")

    payload = {
        "pass": True,
        "probe": "probe1-locate-comparison",
        "unit_id": UNIT_ID,
        "live_verdict": live_cmp.get("live_verdict"),
        "live_file_line": live_cmp.get("live_file_line"),
        "explicit": live_cmp.get("explicit"),
        "fixture_eq_200": fixture.get("file_line"),
        "scanner_both_states": True,
        "signals_agree": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"SUCCESS:{UNIT_ID}-probe1 live={live_cmp.get('explicit')} "
        f"fixture={fixture.get('file_line')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
