#!/usr/bin/env python3
"""Probe 1: each declared hook produces an observable RECEIPT line when triggered."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import dispatcher as D  # noqa: E402
import scenario as S  # noqa: E402

ART = REPO / S.OUT
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def fail(msg: str) -> int:
    print(f"FAILED:TST-0082-probe1 {msg}")
    return 1


def main() -> int:
    S.ensure_fixtures()
    session = D.healthy_session(HERE / "captures" / "probe1-healthy-receipt.txt")
    declared = session["declared_events"]
    fired = session["fired_events"]
    print(
        json.dumps(
            {
                "probe": "probe1-each-hook",
                "declared": declared,
                "fired": fired,
                "fired_count": session["fired_count"],
                "loaded_count": session["loaded_count"],
                "child_written": session["child_written"],
                "parent_pid": session["parent_pid"],
                "child_pids": session["child_pids"],
                "naive_file_count": session["naive_file_count"],
                "reason": session["reason"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    if session["loaded_count"] != len(S.EVENTS):
        return fail(f"loaded={session['loaded_count']} want={len(S.EVENTS)}")
    missing = [event for event in declared if event not in fired]
    if missing:
        return fail(f"events-without-receipt {missing}")
    if session["fired_count"] != len(S.EVENTS):
        return fail(f"fired_count={session['fired_count']} want={len(S.EVENTS)}")
    if not session["child_written"]:
        return fail("receipt-not-from-child-pid")
    if session["parent_pid"] in session["child_pids"]:
        return fail("in-process-forgery parent pid on receipt line")
    executed = [row for row in session["runs"] if row.get("executed")]
    if any(row.get("exit_code") != 0 for row in executed):
        return fail("hook-command-nonzero")
    # Listing is constant across states and is not the pass signal.
    if int(session["naive_file_count"]["sum"]) < 1:
        return fail("writer-or-manifest-missing")

    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        raw = json.loads(text)
        doc = S.receipt_payload(raw)
        if str(doc.get("state") or "").upper() in NOT_DELIVERING:
            return fail(f"self-declared {doc.get('state')}")
        if "SUCCESS:TST-0082" not in text:
            return fail("sentinel-absent")
        tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
        row = tests.get("test_each_hook_produces_an_observable_effect_when_triggered")
        if not row or row.get("result") != "PASS":
            return fail("receipt-test1-not-pass")
        fired_controls = [
            c
            for c in (doc.get("controls") or [])
            if isinstance(c, dict) and c.get("verdict") == "fired"
        ]
        if len(fired_controls) < len(S.EVENTS):
            return fail(f"receipt-fired-controls={len(fired_controls)}")

    print(
        f"fired={session['fired_count']}/{len(S.EVENTS)} "
        f"child_written={session['child_written']} "
        f"naive_sum={session['naive_file_count']['sum']}"
    )
    print("SUCCESS:TST-0082-probe1 each hook produced an observable effect")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
