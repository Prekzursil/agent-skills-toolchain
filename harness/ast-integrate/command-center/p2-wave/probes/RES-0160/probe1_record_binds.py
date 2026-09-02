#!/usr/bin/env python3
"""Probe 1: the decision record actually binds metric + revert + cost.

Re-runs the live back-test and checks the artifact. A record missing any
binding cannot ADOPT. A complete improved record can.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import gate as G  # noqa: E402
import inventory as I  # noqa: E402

ART = REPO / (
    "command-center/research/gem-hunt/"
    "RES-0160-gem-adoption-gate-with-measured-improvement.json"
)
SCHEMA = REPO / "command-center/schema/design-spec.schema.json"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def main() -> int:
    if not ART.is_file():
        print("FAILED:RES-0160-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in NOT_DELIVERING:
        print(f"FAILED:RES-0160-probe1 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:RES-0160" not in text:
        print("FAILED:RES-0160-probe1 sentinel-absent")
        return 1

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft7Validator.check_schema(schema)
    jsonschema.Draft7Validator(schema).validate(doc)
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"$schema": "http://json-schema.org/draft-07/schema#"},
    ):
        if not list(jsonschema.Draft7Validator(schema).iter_errors(garbage)):
            print("FAILED:RES-0160-probe1 schema accepted garbage")
            return 1

    spec = (doc.get("specification") or {}).get("decision_record") or {}
    bindings = spec.get("required_bindings") or []
    if list(bindings) != list(G.BINDINGS):
        print(f"FAILED:RES-0160-probe1 bindings mismatch {bindings}")
        return 1

    missing_metric = G.evaluate_record({"mechanism_id": "probe1-no-metric"})
    if missing_metric["backtest_verdict"] != "WOULD-NOT-HAVE-PASSED":
        print("FAILED:RES-0160-probe1 no-metric was not WOULD-NOT-HAVE-PASSED")
        return 1
    if missing_metric["decision"] != "REJECT":
        print("FAILED:RES-0160-probe1 no-metric did not REJECT")
        return 1

    incomplete = G.evaluate_record(
        {
            "mechanism_id": "probe1-no-cost",
            "named_metric": {
                "id": "x",
                "before": False,
                "after": True,
                "direction": "false_to_true",
            },
            "revert_trigger": {"predicate": "x reverts"},
        }
    )
    if incomplete["decision"] != "PARK":
        print(f"FAILED:RES-0160-probe1 unbound cost decision={incomplete['decision']}")
        return 1
    if incomplete["backtest_verdict"] != "WOULD-NOT-HAVE-PASSED":
        print("FAILED:RES-0160-probe1 unbound cost back-test passed")
        return 1

    complete = G.evaluate_record(G.complete_example())
    if complete["decision"] != "ADOPT" or complete["backtest_verdict"] != "WOULD-HAVE-PASSED":
        print(f"FAILED:RES-0160-probe1 complete example {complete}")
        return 1

    live = I.run_backtest()
    art_n = (doc.get("back_test") or {}).get("n")
    live_n = live["population"]["n"]
    art_pass = (doc.get("back_test") or {}).get("would_have_passed")
    live_pass = live["population"]["would_have_passed"]
    if art_n != live_n or art_pass != live_pass:
        print(
            f"FAILED:RES-0160-probe1 artifact != live back-test "
            f"art=({art_n},{art_pass}) live=({live_n},{live_pass})"
        )
        return 1

    art_ids = [
        r.get("mechanism_id")
        for r in (doc.get("back_test") or {}).get("verdicts") or []
    ]
    live_ids = [r["mechanism_id"] for r in live["population"]["rows"]]
    if art_ids != live_ids:
        print(f"FAILED:RES-0160-probe1 verdict ids drifted art={art_ids} live={live_ids}")
        return 1

    print(
        f"binds={list(G.BINDINGS)} no_metric=WOULD-NOT-HAVE-PASSED "
        f"unbound_cost=PARK complete=ADOPT n={live_n} passed={live_pass}"
    )
    print("SUCCESS:RES-0160-probe1 decision record binds metric+revert+cost")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
