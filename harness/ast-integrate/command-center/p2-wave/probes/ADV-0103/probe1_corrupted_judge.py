#!/usr/bin/env python3
"""Probe 1: corrupted judge on a checkable question via execute_spec.

Control: honest judge + three correct jurors; SDK publishes 4.
Attack: only the judge answers 5. Record whether the shipped SDK
output is wrong. The judge-final overlay is the contrast that can go red.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import mechanism as M  # noqa: E402

ART = REPO / (
    "command-center/adversarial/"
    "ADV-0103-moderator-judge-single-point-failure.json"
)
UNIT = "ADV-0103"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    live = M.measure()
    honest = live["control_honest_judge"]
    corrupt = live["probe1_corrupt_judge"]
    overlay = live["overlay_judge_final"]
    payload = {
        "control_honest_published": honest["published_answer"],
        "control_honest_correct": live["sdk_honest_final_correct"],
        "corrupt_judge_answer": live["corrupt_judge_answer"],
        "corrupt_published": corrupt["published_answer"],
        "corrupt_accepted": corrupt["accepted"],
        "corrupt_for": corrupt["for_count"],
        "corrupt_against": corrupt["against_count"],
        "sdk_corrupt_final_wrong": live["sdk_corrupt_final_wrong"],
        "sdk_judge_alone_flipped_outcome": live["sdk_judge_alone_flipped_outcome"],
        "overlay_corrupt_published": overlay["corrupt_published"],
        "overlay_flipped_by_judge_alone": overlay["flipped_by_judge_alone"],
        "deciding_rule": corrupt["deciding_rule"],
    }
    print(json.dumps(payload, sort_keys=True))
    if not live["sdk_honest_final_correct"]:
        return fail("honest-judge control did not publish the correct answer")
    if honest["published_answer"] != M.CORRECT:
        return fail("honest control published_answer != 4")
    if corrupt["judge_answer"] != M.CORRUPT_ANSWER:
        return fail("corrupt run did not inject judge answer 5")
    if corrupt["against_count"] < 1:
        return fail("corrupt judge did not cast an against ballot")
    if corrupt["for_count"] != 3:
        return fail("expected three juror FOR ballots on the checkable proposal")
    if live["sdk_judge_alone_flipped_outcome"]:
        return fail("shipped SDK flipped the checkable answer when only the judge was corrupt")
    if live["sdk_corrupt_final_wrong"]:
        return fail("shipped SDK published a wrong answer under a 3-1 majority")
    if not overlay["flipped_by_judge_alone"]:
        return fail("judge-final overlay did not go red; detector cannot see the pathology")
    if overlay["corrupt_published"] != M.CORRUPT_ANSWER:
        return fail("overlay did not publish the corrupt judge answer")

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        if str(doc.get("state") or "").upper() in {
            "BLOCKED",
            "FAILED",
            "SEVERED",
            "TIMEOUT",
        }:
            return fail(f"artifact self-declared {doc.get('state')}")
        rec = (doc.get("measurements") or {}).get("probe1") or {}
        for key in (
            "sdk_judge_alone_flipped_outcome",
            "sdk_corrupt_final_wrong",
            "sdk_honest_final_correct",
        ):
            if rec.get(key) != live.get(key):
                return fail(
                    f"artifact mismatch {key} rec={rec.get(key)!r} live={live.get(key)!r}"
                )
        control = next(
            (t for t in (doc.get("tests") or []) if t.get("id") == "T-HONEST-JUDGE-CONTROL"),
            None,
        )
        if control is None or control.get("result") != "PASS":
            return fail("honest-judge control missing or not PASS in artifact")
    print("SUCCESS:ADV-0103-probe1 corrupted-judge checkable run recorded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
