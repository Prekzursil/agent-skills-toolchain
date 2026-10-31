#!/usr/bin/env python3
"""Named probe 1 (CC-0003): table-driven, exactly one falsifying case per
condition 1-10, each proving the reducer returns INCOMPLETE for the RIGHT
reason, plus the both-states gold control (the unmutated fixture reaches
COMPLETE -- without it the ten cases could be vacuous).

Recreated 2026-10-25 (wave-2 shard 7) after the original probe tree was lost;
drives platform/lib/completion_predicate.evaluate, the real reducer.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402


def case_1_state_not_success(fx: S.Fixture) -> dict:
    m = copy.deepcopy(fx.receipt)
    m["state"] = "DELIVERED"  # terminal-sounding but not success-class
    r = fx.evaluate(m)
    return dict(n=1, verdict=r.verdict.name, cond=r.condition(1), why="state not success-class")


def case_2_artifact_missing(fx: S.Fixture) -> dict:
    orig = fx.art_path.read_bytes()
    try:
        fx.art_path.unlink()
        r = fx.evaluate()
    finally:
        fx.art_path.write_bytes(orig)
    return dict(n=2, verdict=r.verdict.name, cond=r.condition(2), why="stat says absent")


def case_3_threshold_too_high(fx: S.Fixture) -> dict:
    m = copy.deepcopy(fx.receipt)
    m["min_bytes_threshold"] = m["artifacts"][0]["bytes"] + 100000
    r = fx.evaluate(m)
    return dict(n=3, verdict=r.verdict.name, cond=r.condition(3), why="below effective minimum")


def case_4_wrong_schema(fx: S.Fixture) -> dict:
    r = fx.evaluate(output_schema="command-center/schema/contradiction-register.schema.json")
    return dict(n=4, verdict=r.verdict.name, cond=r.condition(4), why="fails declared schema")


def case_5_sentinel_id_mismatch(fx: S.Fixture) -> dict:
    # Rewrite the on-disk artifact with a sentinel for a DIFFERENT unit; the
    # receipt still claims SUCCESS:FIX-0001. Restore afterwards.
    orig = fx.art_path.read_bytes()
    try:
        doc = json.loads(orig.decode("utf-8"))
        doc["sentinel"] = "SUCCESS:FIX-9999"
        fx.art_path.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
        fx.resync()
        r = fx.evaluate()
    finally:
        fx.art_path.write_bytes(orig)
    return dict(n=5, verdict=r.verdict.name, cond=r.condition(5), why="sentinel embedded id mismatch")


def case_6_anchor_dangling(fx: S.Fixture) -> dict:
    m = copy.deepcopy(fx.receipt)
    for ev in m["evidence"]:
        ev["anchor"] = "platform/lib/no_such_file.py:1"
    r = fx.evaluate(m)
    return dict(n=6, verdict=r.verdict.name, cond=r.condition(6), why="anchor does not resolve")


def case_7_test_fails(fx: S.Fixture) -> dict:
    m = copy.deepcopy(fx.receipt)
    m["tests"][0]["result"] = "FAIL"
    r = fx.evaluate(m)
    return dict(n=7, verdict=r.verdict.name, cond=r.condition(7), why="a recorded test is FAIL")


def case_8_control_not_firing(fx: S.Fixture) -> dict:
    m = copy.deepcopy(fx.receipt)
    m["negative_controls"][0]["fired_on_bad_state"] = False
    r = fx.evaluate(m)
    return dict(n=8, verdict=r.verdict.name, cond=r.condition(8), why="control did not fire on bad state")


def case_9_reviewer_fail(fx: S.Fixture) -> dict:
    m = copy.deepcopy(fx.receipt)
    m["reviewer"]["verdict"] = "FAIL"
    r = fx.evaluate(m)
    return dict(n=9, verdict=r.verdict.name, cond=r.condition(9), why="reviewer verdict is not PASS")


def case_10_open_p1_defect(fx: S.Fixture) -> dict:
    m = copy.deepcopy(fx.receipt)
    m["defects"] = [
        {"id": "FIX-0001-D1", "severity": "P1", "status": "open", "summary": "injected"}
    ]
    r = fx.evaluate(m)
    return dict(n=10, verdict=r.verdict.name, cond=r.condition(10), why="open P1 defect attached")


CASES = [
    case_1_state_not_success,
    case_2_artifact_missing,
    case_3_threshold_too_high,
    case_4_wrong_schema,
    case_5_sentinel_id_mismatch,
    case_6_anchor_dangling,
    case_7_test_fails,
    case_8_control_not_firing,
    case_9_reviewer_fail,
    case_10_open_p1_defect,
]


def main() -> int:
    fx = S.Fixture()
    failures: list[str] = []
    try:
        # Both-states gold control: the unmutated fixture MUST reach COMPLETE,
        # otherwise every falsifying case below is vacuous.
        gold = fx.evaluate()
        print("gold-control verdict=%s unsatisfied=%s not_checked=%s" % (
            gold.verdict.value, gold.unsatisfied, gold.not_checked))
        if gold.verdict is not S.CP.Verdict.COMPLETE:
            for c in gold.conditions:
                if c.outcome is not S.CP.Outcome.SATISFIED:
                    print("  gold c%d %s: %s" % (c.n, c.outcome.value, c.basis[:160]))
            print("FAILED:CC-0003-probe1 gold fixture does not reach COMPLETE")
            return 1

        rows = []
        for case in CASES:
            row = case(fx)
            ok = (
                row["verdict"] == "INCOMPLETE"
                and row["cond"].outcome is not S.CP.Outcome.SATISFIED
            )
            rows.append((row, ok))
            print("case c%-2d %-11s c%d=%-12s %s" % (
                row["n"], row["verdict"], row["n"], row["cond"].outcome.value,
                "OK" if ok else "NOT-FALSIFIED"))
            if not ok:
                failures.append("c%d verdict=%s outcome=%s" % (
                    row["n"], row["verdict"], row["cond"].outcome.value))
        # Restore the artifact mutated by case 5 before resync-sensitive checks.
        fx.resync()
    finally:
        fx.cleanup()

    if failures:
        print("FAILED:CC-0003-probe1 %s" % "; ".join(failures))
        return 1
    print("SUCCESS:CC-0003-probe1 table-driven 10/10 falsified; gold reaches COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
