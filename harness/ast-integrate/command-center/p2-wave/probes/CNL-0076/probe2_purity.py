#!/usr/bin/env python3
"""Probe 2: purity enforced, not assumed.

An expression with a side effect is REJECTED at bind time. A pure comparison
on the same snapshot is ACCEPTED and evaluated. Negative control is printed
verbatim: what the check does on the state it is meant to reject.
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
FIX = HERE / "fixtures" / "purity.json"

NEGATIVE_CONTROL_VERBATIM = (
    "NEGATIVE-CONTROL: on impure op=assign (unique_ideas := 999) "
    "check_purity.verdict=REJECTED reasons contain impure-op:assign; "
    "run_round(eval_point=end-of-round) sets evaluated=False halt=False "
    "rejected=True and does not enter eval_ast. Bypassing the gate and calling "
    "eval_ast on the frozen snapshot raises PurityError impure-or-unknown-op:assign; "
    "halt remains false. The state this check is meant to reject is any stopping "
    "expression whose AST contains assign/call/mutate/write/inc/effect."
)


def main() -> int:
    fx = json.loads(FIX.read_text(encoding="utf-8"))
    snap = R.freeze(fx["snapshot"])

    pure_p = R.check_purity(fx["pure"])
    asg_p = R.check_purity(fx["impure_assign"])
    call_p = R.check_purity(fx["impure_call"])
    print(f"pure_verdict={pure_p['verdict']} reasons={pure_p['reasons']}")
    print(f"assign_verdict={asg_p['verdict']} reasons={asg_p['reasons']}")
    print(f"call_verdict={call_p['verdict']} reasons={call_p['reasons']}")

    if not pure_p["accepted"] or pure_p["rejected"]:
        print("FAILED:CNL-0076-probe2 pure expression was rejected")
        return 1
    if not asg_p["rejected"] or asg_p["accepted"]:
        print("FAILED:CNL-0076-probe2 assign was not rejected")
        return 1
    if not any("impure-op:assign" in r for r in asg_p["reasons"]):
        print("FAILED:CNL-0076-probe2 assign reason missing")
        return 1
    if not call_p["rejected"] or call_p["accepted"]:
        print("FAILED:CNL-0076-probe2 call was not rejected")
        return 1
    if not any("impure-op:call" in r for r in call_p["reasons"]):
        print("FAILED:CNL-0076-probe2 call reason missing")
        return 1

    driven_pure = R.run_round(
        fx["pure"],
        [{"id": "t1", "metrics": fx["snapshot"]}],
        eval_point="end-of-round",
    )
    driven_asg = R.run_round(
        fx["impure_assign"],
        [{"id": "t1", "metrics": fx["snapshot"]}],
        eval_point="end-of-round",
    )
    print(
        f"pure_run evaluated={driven_pure['evaluated']} halt={driven_pure['halt']} "
        f"result={driven_pure['result']!r}"
    )
    print(
        f"assign_run evaluated={driven_asg['evaluated']} halt={driven_asg['halt']} "
        f"rejected={driven_asg['rejected']}"
    )
    if not driven_pure["evaluated"] or driven_pure["halt"] is not False:
        print("FAILED:CNL-0076-probe2 pure run did not evaluate to continue")
        return 1
    if driven_asg["evaluated"] or not driven_asg["rejected"] or driven_asg["halt"]:
        print("FAILED:CNL-0076-probe2 assign run must be rejected and not halt")
        return 1

    bypass = R.force_eval_impure(fx["impure_assign"], snap)
    print(
        f"bypass_assign raised={bypass['raised']} error_type={bypass.get('error_type')} "
        f"error={bypass.get('error')!r} halt={bypass['halt']}"
    )
    if not bypass["raised"] or bypass["halt"]:
        print("FAILED:CNL-0076-probe2 bypassed assign must raise and not halt")
        return 1
    if bypass.get("error_type") != "PurityError":
        print("FAILED:CNL-0076-probe2 bypassed assign expected PurityError")
        return 1

    print(NEGATIVE_CONTROL_VERBATIM)

    if not ART.is_file():
        print("FAILED:CNL-0076-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print(f"FAILED:CNL-0076-probe2 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:CNL-0076" not in ART.read_text(encoding="utf-8"):
        print("FAILED:CNL-0076-probe2 sentinel absent")
        return 1
    answers = doc.get("answers") or {}
    if answers.get("side_effect_free") is not True:
        print("FAILED:CNL-0076-probe2 artifact does not require purity")
        return 1
    nc = doc.get("negative_control") or {}
    if "impure-op:assign" not in str(nc):
        print("FAILED:CNL-0076-probe2 artifact negative_control missing assign reject")
        return 1
    print("SUCCESS:CNL-0076-probe2 side-effect expression REJECTED purity enforced")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
