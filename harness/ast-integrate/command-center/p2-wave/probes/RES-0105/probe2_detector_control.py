#!/usr/bin/env python3
"""Probe 2: detector control — known-good fires; known-broken always-zero is silent."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import contract as C  # noqa: E402
import harness as H  # noqa: E402

ART = REPO / C.OUTPUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:RES-0105-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    both = H.run_detector_both_states()
    print(json.dumps({
        "fires_on_known_good": both.get("fires_on_known_good", both.get("fires_on_known_good")),
        "silent_on_known_broken": both.get("fires_on_known_broken", both.get("fires_on_known_broken")),
        "both_states": both.get("both_states", both.get("both_states")),
        "known_good_output": both["known_good"]["output"],
        "known_broken_output": both["known_broken"]["output"],
    }, sort_keys=True))

    good_ok = both["known_good"]["detector_ok"] is True
    broken_ok = both["known_broken"]["detector_ok"] is False
    if not good_ok:
        return fail("detector silent on known-good fixture")
    if not broken_ok:
        return fail("detector silent on known-broken always-zero fixture")
    if not (both.get("both_states") or both.get("both_states")):
        return fail("both_states false")

    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    rec = report.get("detector_control") or doc.get("detector_control") or {}
    if rec.get("fired_on_known_good") is not True:
        return fail("artifact did not record fired_on_known_good")
    if rec.get("silent_on_known_broken") is not True:
        return fail("artifact did not record silent_on_known_broken")
    if rec.get("both_states") is not True:
        return fail("artifact both_states is not true")
    kg = rec.get("known_good_output") or {}
    kb = rec.get("known_broken_output") or {}
    if kg.get("ok") is not True:
        return fail("artifact known-good output ok is not true")
    if kb.get("ok") is not False:
        return fail("artifact known-broken output ok is not false")

    rev = doc.get("reviewer") or {}
    if rev.get("verdict") != "PASS" or rev.get("independent") is not True:
        return fail("reviewer record missing")
    print("reviewer_id=" + str(rev.get("reviewer_id")))
    print("SUCCESS:RES-0105-probe2 detector-control known-good fires, known-broken silent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
