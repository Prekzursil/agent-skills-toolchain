#!/usr/bin/env python3
"""Probe 1: flapping-predicate fixture produces a deterministic halt/continue.

Independent recount: last-snapshot eval (eval_ast + eval_rpn) must match the
cadence driver, which only samples at end-of-round. Mid-turn evaluation is
refused even when the live metrics would be true.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(HERE))
import runtime as R  # noqa: E402

ART = REPO / (
    "command-center/design/council/"
    "CNL-0076-stopping-expression-runtime-evaluation-semantics.schema.json"
)
FIX = HERE / "fixtures" / "flapping_round.json"


def _path_bools(intra: list[dict]) -> list[bool]:
    out = []
    for row in intra:
        v = row["would_be"]
        if v is True:
            out.append(True)
        elif v is False:
            out.append(False)
        else:
            out.append(v)
    return out


def main() -> int:
    fx = json.loads(FIX.read_text(encoding="utf-8"))
    expr = fx["expression"]
    purity = R.check_purity(expr)
    print(f"purity_verdict={purity['verdict']}")
    if not purity["accepted"]:
        print("FAILED:CNL-0076-probe1 flap expression rejected as impure")
        return 1

    for case in fx["cases"]:
        driven = R.run_round(expr, case["turns"], eval_point="end-of-round")
        recounted = R.recount_last_snapshot(expr, case["turns"])
        path = _path_bools(driven["intra_round_path"])
        print(
            f"case={case['id']} halt={driven['halt']} result={driven['result']!r} "
            f"recount={recounted!r} path={path}"
        )
        if driven["cadence_violation"] or driven["rejected"]:
            print(f"FAILED:CNL-0076-probe1 {case['id']} not evaluated")
            return 1
        if driven["result"] != recounted:
            print(
                f"FAILED:CNL-0076-probe1 {case['id']} driver/recount disagree "
                f"{driven['result']!r} vs {recounted!r}"
            )
            return 1
        if driven["halt"] is not case["expected_halt"]:
            print(
                f"FAILED:CNL-0076-probe1 {case['id']} halt={driven['halt']} "
                f"expected={case['expected_halt']}"
            )
            return 1
        if driven["result"] is not case["expected_result"]:
            print(
                f"FAILED:CNL-0076-probe1 {case['id']} result={driven['result']!r} "
                f"expected={case['expected_result']!r}"
            )
            return 1
        if path != case["expected_path"]:
            print(
                f"FAILED:CNL-0076-probe1 {case['id']} path={path} "
                f"expected={case['expected_path']}"
            )
            return 1
        if driven["result"] != driven["rpn_result"]:
            print("FAILED:CNL-0076-probe1 ast/rpn disagreement")
            return 1

    flap = next(c for c in fx["cases"] if c["id"] == "flap-true-then-false")
    mid = R.run_round(expr, flap["turns"][:1], eval_point="mid-turn")
    eot = R.run_round(expr, flap["turns"][:1], eval_point="end-of-turn")
    print(
        f"mid-turn cadence_violation={mid['cadence_violation']} halt={mid['halt']} "
        f"would_be_true_if_sampled={flap['turns'][0]['metrics']['unique_ideas'] >= 100}"
    )
    print(
        f"end-of-turn cadence_violation={eot['cadence_violation']} halt={eot['halt']}"
    )
    if not mid["cadence_violation"] or mid["halt"] or mid["evaluated"]:
        print("FAILED:CNL-0076-probe1 mid-turn must refuse evaluation and not halt")
        return 1
    if not eot["cadence_violation"] or eot["halt"] or eot["evaluated"]:
        print("FAILED:CNL-0076-probe1 end-of-turn must not take the halt decision")
        return 1

    # Determinism: same fixture twice, identical halt vector.
    again = [
        R.run_round(expr, c["turns"], eval_point="end-of-round")["halt"]
        for c in fx["cases"]
    ]
    first = [
        R.run_round(expr, c["turns"], eval_point="end-of-round")["halt"]
        for c in fx["cases"]
    ]
    print(f"determinism_repeat={first == again} halt_vector={first}")
    if first != again:
        print("FAILED:CNL-0076-probe1 non-deterministic halt vector")
        return 1

    if not ART.is_file():
        print("FAILED:CNL-0076-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print(f"FAILED:CNL-0076-probe1 self-declared {doc.get('state')}")
        return 1
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:CNL-0076" not in text:
        print("FAILED:CNL-0076-probe1 sentinel absent")
        return 1
    answers = doc.get("answers") or {}
    if answers.get("cadence") != "end-of-round":
        print(f"FAILED:CNL-0076-probe1 artifact cadence {answers.get('cadence')!r}")
        return 1
    if answers.get("flapping_rule") != "sample-at-end-of-round-no-latch":
        print("FAILED:CNL-0076-probe1 artifact flapping_rule mismatch")
        return 1
    print("SUCCESS:CNL-0076-probe1 flapping-predicate deterministic end-of-round sample")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
