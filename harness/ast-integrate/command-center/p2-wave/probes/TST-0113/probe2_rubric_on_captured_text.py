#!/usr/bin/env python3
"""Probe 2: each captured message scores on all three rubric parts.

Independent of probe 1: re-triggers, scores the captured text, and plants
bare 'operation failed' controls that must not pass. Does not read message
templates out of client_negotiate.py.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from inventory import UNIT, capture_all  # noqa: E402
from rubric import score_message  # noqa: E402

ART = REPO / "command-center" / "receipts" / f"{UNIT}.json"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    cap = capture_all()
    live_scores = []
    for row in cap["rows"]:
        scored = score_message(row["captured_text"])
        live_scores.append({"id": row["id"], **scored})
        print(
            f"score {row['id']} {scored['score']}/{scored['max']} "
            f"pass={scored['pass']} text={row['captured_text'][:120]}"
        )
        if not scored["pass"]:
            return fail(f"{row['id']} captured text failed rubric: {scored}")
        if scored["scored_from"] != "captured-text":
            return fail("scorer claimed a non-captured basis")

    bare_scores = []
    for msg in cap["bare_messages"]:
        scored = score_message(msg)
        bare_scores.append({"planted": msg, **scored})
        if scored["pass"]:
            return fail(f"bare message unexpectedly passed: {msg!r}")
        if scored["parts"]["what_to_do"]["pass"] or scored["parts"]["why"]["pass"]:
            return fail(f"bare message must fail why and what_to_do: {msg!r}")
    if not bare_scores:
        return fail("no planted bare messages")

    swapped = score_message("operation failed.")
    if swapped["pass"]:
        return fail("swapped generic message passed the rubric")

    print(
        json.dumps(
            {
                "probe": "probe2-rubric-on-captured-text",
                "unit_id": UNIT,
                "live_all_pass": all(s["pass"] for s in live_scores),
                "bare_all_fail": all(not s["pass"] for s in bare_scores),
                "n_live": len(live_scores),
                "n_bare": len(bare_scores),
            },
            sort_keys=True,
        )
    )

    if not ART.is_file():
        return fail("receipt missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if f"SUCCESS:{UNIT}" not in ART.read_text(encoding="utf-8"):
        return fail("sentinel absent")
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    t2 = tests.get("test_each_message_scores_on_all_three_rubric_parts") or {}
    if t2.get("result") != "PASS":
        return fail("receipt test_each_message_scores_on_all_three_rubric_parts not PASS")
    nc = doc.get("negative_controls") or []
    if not any(x.get("id") == "bare-operation-failed" and x.get("fired_on_bad") for x in nc):
        return fail("receipt missing bare-operation-failed negative control")
    rec_by_id = {p["id"]: p for p in (doc.get("triggered_paths") or [])}
    for scored in live_scores:
        rec = rec_by_id.get(scored["id"]) or {}
        if rec.get("captured_text") != scored["captured_text"]:
            return fail(f"{scored['id']} receipt text drifted from live capture")
        if rec.get("rubric", {}).get("pass") is not True:
            return fail(f"{scored['id']} receipt rubric not pass")
        if rec.get("rubric", {}).get("scored_from") != "captured-text":
            return fail(f"{scored['id']} receipt scores not marked captured-text")

    print("live_all_pass=True bare_all_fail=True swapped_generic_fails=True")
    print(f"SUCCESS:{UNIT}-probe2 each message scores on all three rubric parts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
