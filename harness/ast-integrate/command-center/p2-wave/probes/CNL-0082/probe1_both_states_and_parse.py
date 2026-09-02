#!/usr/bin/env python3
"""Probe 1: A10 parse-unchanged + both-states FIRE/SILENT + time-arm split.

A detector silent in both states measures nothing. The time arm of the
disjunction must be logged separately from evidence_saturation.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from a10_grammar import (  # noqa: E402
    SIX_SPEC_EXAMPLES,
    SPEC_EXPR,
    accepted_unchanged,
    parse_all_six,
)
from eval_stop import evaluate_fixture  # noqa: E402
from load_fixtures import load  # noqa: E402


def _check(run: dict, fire: bool, arm: str, sat: bool, reason: str) -> None:
    d = run["decision"]
    det = run["detector"]
    fid = run["fixture_id"]
    if d["fires"] is not fire:
        raise SystemExit(f"FAILED:CNL-0082-probe1 {fid} fires={d['fires']} want {fire}")
    if d["which_arm"] != arm:
        raise SystemExit(f"FAILED:CNL-0082-probe1 {fid} arm={d['which_arm']!r} want {arm!r}")
    if bool(det["evidence_saturation"]) is not sat:
        raise SystemExit(
            f"FAILED:CNL-0082-probe1 {fid} saturation={det['evidence_saturation']} want {sat}"
        )
    if det["reason"] != reason:
        raise SystemExit(f"FAILED:CNL-0082-probe1 {fid} reason={det['reason']!r} want {reason!r}")
    if fire and sat and d["saturation_arm"] is not True:
        raise SystemExit(f"FAILED:CNL-0082-probe1 {fid} saturation_arm not true")
    if arm == "time_minutes" and d["saturation_arm"] is True:
        raise SystemExit(f"FAILED:CNL-0082-probe1 {fid} time arm masked as saturation")


def main() -> int:
    if SPEC_EXPR != "evidence_saturation == true OR time_minutes >= 180":
        print("FAILED:CNL-0082-probe1 spec string mutated")
        return 1
    ast = accepted_unchanged(SPEC_EXPR)
    if ast.get("op") != "OR":
        print("FAILED:CNL-0082-probe1 AST is not OR", ast)
        return 1
    six = parse_all_six()
    if len(six) != 6:
        print("FAILED:CNL-0082-probe1 six-example parse count", len(six))
        return 1
    for src, row in zip(SIX_SPEC_EXAMPLES, six):
        if row["source"] != src:
            print("FAILED:CNL-0082-probe1 example rewritten", src)
            return 1

    sat = evaluate_fixture(load("saturated-12.json"))
    uns = evaluate_fixture(load("unsaturated-12.json"))
    fat = evaluate_fixture(load("fatigue-repeat-queries.json"))
    tim = evaluate_fixture(load("time-arm-180.json"))
    mir = evaluate_fixture(load("near-identical-mirrors.json"))

    _check(sat, True, "evidence_saturation", True, "saturated")
    _check(uns, False, "none", False, "still_yielding")
    _check(fat, False, "none", False, "search_fatigue")
    _check(tim, True, "time_minutes", False, "still_yielding")
    _check(mir, True, "evidence_saturation", True, "saturated")

    if sat["detector"]["fire_after_query_index"] is None:
        print("FAILED:CNL-0082-probe1 saturated fire index missing")
        return 1
    if sat["detector"]["independent_mechanisms_found"] != 12:
        print("FAILED:CNL-0082-probe1 saturated found", sat["detector"]["independent_mechanisms_found"])
        return 1
    if sat["detector"]["missed_independent_if_stop_here"] != 0:
        print("FAILED:CNL-0082-probe1 miss_rate", sat["detector"]["missed_independent_if_stop_here"])
        return 1
    if mir["detector"]["independent_mechanisms_found"] != 1:
        print("FAILED:CNL-0082-probe1 mirrors not collapsed", mir["detector"])
        return 1
    if mir["detector"]["ground_truth_independent_count"] != 1:
        print("FAILED:CNL-0082-probe1 mirrors GT", mir["detector"]["ground_truth_independent_count"])
        return 1

    # Never-firing-detector masking: unsaturated at t=40 is false on BOTH arms.
    if uns["decision"]["time_arm"] is True or uns["decision"]["saturation_arm"] is True:
        print("FAILED:CNL-0082-probe1 unsaturated leaked an arm")
        return 1

    raw = {
        "spec_expr": SPEC_EXPR,
        "ast": ast,
        "six_parsed": [r["source"] for r in six],
        "saturated": {
            "fires": sat["decision"]["fires"],
            "arm": sat["decision"]["which_arm"],
            "reason": sat["detector"]["reason"],
            "found": sat["detector"]["independent_mechanisms_found"],
            "fire_after_query_index": sat["detector"]["fire_after_query_index"],
            "missed": sat["detector"]["missed_independent_if_stop_here"],
        },
        "unsaturated": {
            "fires": uns["decision"]["fires"],
            "arm": uns["decision"]["which_arm"],
            "reason": uns["detector"]["reason"],
            "found": uns["detector"]["independent_mechanisms_found"],
        },
        "fatigue": {
            "fires": fat["decision"]["fires"],
            "reason": fat["detector"]["reason"],
        },
        "time_arm": {
            "fires": tim["decision"]["fires"],
            "arm": tim["decision"]["which_arm"],
            "saturation_arm": tim["decision"]["saturation_arm"],
            "time_arm": tim["decision"]["time_arm"],
        },
        "mirrors": {
            "fires": mir["decision"]["fires"],
            "independent": mir["detector"]["independent_mechanisms_found"],
            "source_ids_seen": mir["detector"]["source_ids_seen"],
        },
        "pass": True,
    }
    (HERE / "probe1-both-states.raw.json").write_text(
        json.dumps(raw, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(raw, sort_keys=True))
    print(
        "FIRE saturated arm=evidence_saturation SILENT unsaturated "
        f"fatigue_reason={fat['detector']['reason']} "
        f"time_arm={tim['decision']['which_arm']} "
        f"mirrors_independent={mir['detector']['independent_mechanisms_found']}"
    )
    print("SUCCESS:CNL-0082-probe1 both-states parse-unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
