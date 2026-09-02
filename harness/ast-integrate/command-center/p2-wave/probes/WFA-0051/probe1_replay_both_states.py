#!/usr/bin/env python3
"""Probe 1: IR retry+DAG replay worked case + both-states control.

GOOD: two runs with sorted ready-set → identical expected sequence.
BAD: reverse ready-set sort → sequences differ (diamond children swap).
Independent of probe 2 (architecture-lane routing / file-fake mutant).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import replay as R  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0051-adapter-dag-schedulers.json"
SENTINEL = "SUCCESS:WFA-0051"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0051-probe1 {msg}")
    return 1


def main() -> int:
    worked = R.worked_case()
    broken = R.broken_case_reverse_ready()
    jitter = R.refuse_jitter_policy()
    if not worked["identical"]:
        return fail("GOOD arm: two runs were not identical")
    if not worked["matches_expected"]:
        return fail(f"GOOD arm sequence {worked['run_1']}")
    if not broken["differ"]:
        return fail("BAD arm: reverse ready-set did not change the sequence")
    if broken["good"] == broken["bad"]:
        return fail("BAD arm sequences equal")
    if not jitter["refused"]:
        return fail("jitter policy was not refused")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    if SENTINEL not in text:
        return fail("sentinel absent")
    exp = doc.get("replay_experiment") or {}
    if exp.get("good_run_1") != worked["run_1"]:
        return fail("artifact good_run_1 != live")
    if exp.get("good_run_2") != worked["run_2"]:
        return fail("artifact good_run_2 != live")
    if exp.get("bad_run") != broken["bad"]:
        return fail("artifact bad_run != live")
    both = (doc.get("both_states") or {}).get("replay") or {}
    if both.get("good_identical") is not True:
        return fail("artifact both_states.replay.good_identical not true")
    if both.get("bad_reverse_ready_differs") is not True:
        return fail("artifact both_states.replay.bad_reverse_ready_differs not true")
    tests = {t["id"]: t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    if tests.get("deterministic-replay-worked-case", {}).get("pass") is not True:
        return fail("artifact replay test not pass")
    if tests.get("replay-both-states", {}).get("pass") is not True:
        return fail("artifact replay-both-states not pass")

    payload = {
        "bad_differ": broken["differ"],
        "good_identical": worked["identical"],
        "jitter_refused": jitter["refused"],
        "pass": True,
        "probe": "probe1-replay-both-states",
        "sequence": worked["run_1"],
        "unit_id": "WFA-0051",
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "good_identical=True bad_differ=True "
        f"seq={worked['run_1']}"
    )
    print("SUCCESS:WFA-0051-probe1 IR retry+DAG replay; reverse-ready is the BAD arm")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

