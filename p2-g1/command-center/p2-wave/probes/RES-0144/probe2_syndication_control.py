#!/usr/bin/env python3
"""Probe 2: five verbatim syndicated copies must score low-independence.

Both-states: unique-URL poller treats each copy as ORIGINATING (high
independence). If the rubric also scores them high, the independence axis
measures nothing. Independent originating bodies must not be SYNDICATED.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import corpus as C  # noqa: E402
import rater_a as A  # noqa: E402
import rater_b as B  # noqa: E402
import score as S  # noqa: E402

ART = REPO / "command-center/research/evidence-quality/RES-0144-two-axis-source-quality-rubric.json"
UNIT = "RES-0144"
SENTINEL = "SUCCESS:RES-0144"


def fail(msg: str) -> int:
    print(f"FAILED:RES-0144-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact-absent")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")

    live = S.run()
    ctrl = live["controls"]
    if not ctrl.get("pass"):
        return fail(f"both-states pass={ctrl}")
    if not live.get("syndicated_all_low_a") or not live.get("syndicated_all_low_b"):
        return fail("syndicated-copies-not-low-independence")
    false_wake = ctrl.get("false_wake_rate")
    if false_wake is None or float(false_wake) != 0.0:
        return fail(f"false_wake_rate={false_wake}")
    poller_rate = ctrl.get("poller_false_independent_rate")
    if poller_rate is None or float(poller_rate) != 1.0:
        return fail("poller-did-not-score-copies-as-originating")

    rec = {c.get("id"): c for c in (doc.get("controls") or []) if isinstance(c, dict)}
    for case in ctrl["cases"]:
        stored = rec.get(case["id"])
        if not stored:
            return fail(f"missing-control {case['id']}")
        if stored.get("watcher_wake") != case["watcher_wake"]:
            return fail(f"control-drift {case['id']} watcher")
        if stored.get("poller_wake") != case["poller_wake"]:
            return fail(f"control-drift {case['id']} poller")
        if stored.get("verdict") != "PASS":
            return fail(f"control-verdict {case['id']} {stored.get('verdict')}")

    synd = set(C.syndicated_ids())
    a_map = {r["id"]: r for r in live["rater_a"]}
    b_map = {r["id"]: r for r in live["rater_b"]}
    for sid in synd:
        if a_map[sid]["independence"] != "SYNDICATED":
            return fail(f"rater-a {sid} {a_map[sid]['independence']}")
        if b_map[sid]["independence"] != "SYNDICATED":
            return fail(f"rater-b {sid} {b_map[sid]['independence']}")
        if S.poller_independence({"id": sid, "url": sid}, live["corpus"]) != "ORIGINATING":
            return fail(f"poller {sid}")

    for sid in C.independent_originating_ids():
        if a_map[sid]["independence"] == "SYNDICATED":
            return fail(f"independent-flagged-a {sid}")
        if b_map[sid]["independence"] == "SYNDICATED":
            return fail(f"independent-flagged-b {sid}")

    # Repair: replace verbatim bodies with unique text. Cluster must dissolve.
    repaired = copy.deepcopy(live["corpus"])
    for i, sid in enumerate(C.syndicated_ids()):
        for src in repaired:
            if src["id"] == sid:
                src["body"] = (
                    f"Completely unique originating laboratory note {sid} token{i} "
                    f"vocabulary-{sid}-only about a distinct local experiment."
                )
    ra = A.score_all(repaired)
    rb = B.score_all(repaired)
    still_a = [r["id"] for r in ra if r["id"] in synd and r["low_independence"]]
    still_b = [r["id"] for r in rb if r["id"] in synd and r["low_independence"]]
    if still_a or still_b:
        return fail(f"repair-still-syndicated a={still_a} b={still_b}")

    rec_rate = (doc.get("measurements") or {}).get("false_wake_rate")
    if float(rec_rate) != 0.0:
        return fail(f"artifact-false-wake {rec_rate}")

    print(
        "syndicated_low_a=5 syndicated_low_b=5 poller_originating=5 "
        "independent_not_syndicated=5 repair_dissolved=True"
    )
    print("fired_on_copies=True silent_on_independent=True poller_fires_on_both=True")
    print("SUCCESS:RES-0144-probe2 syndication negative control: copies scored low-independence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
