"""Run the TST-0037 conformance suite against the contract validator and production."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import cases as C
import contract_validator as CV
import inventory as INV
import production as P
from constructs import ORDER, QUESTION


def _pass(cond: bool) -> str:
    return "PASS" if cond else "FAIL"


def run(repo: Path) -> dict[str, Any]:
    inv = INV.scan(repo)
    case_rows = []
    fail = False
    for spec in C.materialize():
        contract_ids = CV.ids_of(spec["doc"])
        prod_ids = P.ids_of(repo, spec["doc"])
        expect_c = set(spec["expect_contract"])
        contract_ok = expect_c <= contract_ids if expect_c else contract_ids == set()
        if spec["expect_production_empty"]:
            prod_ok = prod_ids == set()
        else:
            prod_ok = set(spec["expect_production_contains"]) <= prod_ids
        absent = set(spec.get("expect_production_absent") or ())
        absent_ok = not (absent & prod_ids)
        row_ok = contract_ok and prod_ok and absent_ok
        if not row_ok:
            fail = True
        case_rows.append(
            {
                "id": spec["id"],
                "construct": spec["construct"],
                "rule": spec["rule"],
                "role": spec["role"],
                "contract_ids": sorted(contract_ids),
                "production_ids": sorted(prod_ids),
                "expect_contract": sorted(expect_c),
                "contract_ok": contract_ok,
                "production_ok": prod_ok and absent_ok,
                "ok": row_ok,
            }
        )

    by_construct: dict[str, list[dict]] = {cid: [] for cid in ORDER}
    for row in case_rows:
        by_construct.setdefault(row["construct"], []).append(row)

    table = []
    for inv_row in inv["rows"]:
        cid = inv_row["construct"]
        suite_rows = by_construct.get(cid) or []
        goods = [r for r in suite_rows if r["role"] == "good"]
        bads = [r for r in suite_rows if r["role"] == "bad"]
        suite_case = bool(goods) and bool(bads) and all(r["ok"] for r in suite_rows)
        both_states = suite_case
        table.append(
            {
                "construct": cid,
                "schema_rule": inv_row["schema_rule"],
                "schema_rule_production": (
                    ",".join(inv_row["schema_rule_ids"] or inv_row["schema_rule_closed_types"])
                    or "ABSENT"
                ),
                "conformance_case": suite_case,
                "conformance_case_production": inv_row["conformance_case_production"],
                "conformance_case_suite": sorted(r["id"] for r in suite_rows),
                "production_validator": inv_row["production_validator"],
                "both_states": both_states,
                "spec_classes_present": inv_row["spec_classes_present"],
                "not_this": inv_row.get("not_this"),
            }
        )

    missing_validator = [
        r["construct"] for r in table if not r["production_validator"]
    ]
    suite_covers = all(r["conformance_case"] and r["both_states"] for r in table)
    negative_per_rule = all(
        any(r["role"] == "bad" and r["ok"] for r in by_construct[cid]) for cid in ORDER
    )
    production_discriminates_fanout = any(
        r["id"] == "fan-out/empty" and r["ok"] for r in case_rows
    ) and any(r["id"] == "fan-out/good" and r["ok"] for r in case_rows)

    loop_good = next(r for r in case_rows if r["id"] == "loop-with-convergence/good")
    loop_bad = next(r for r in case_rows if r["id"] == "loop-with-convergence/unbounded")
    production_loop_undifferentiated = (
        "unknown-node-type" in loop_good["production_ids"]
        and "unknown-node-type" in loop_bad["production_ids"]
        and "loop-unbounded" not in loop_good["production_ids"]
        and "loop-unbounded" not in loop_bad["production_ids"]
        and loop_good["contract_ok"]
        and loop_bad["contract_ok"]
    )

    tests = [
        {
            "id": "conformance-suite-written-before-broad-implementation",
            "result": _pass(suite_covers and not fail),
            "note": "seven constructs each have a contract schema rule, a good twin, and a negative fixture",
        },
        {
            "id": "negative-case-per-contract-rule",
            "result": _pass(negative_per_rule),
            "note": "at least one failing fixture per named construct rule",
        },
        {
            "id": "both-states-suite-fails-on-nonconforming-input",
            "result": _pass(suite_covers and production_discriminates_fanout),
            "note": "good twin is clean on the contract validator; planted nonconforming input is not",
        },
        {
            "id": "production-cannot-discriminate-unbounded-loop",
            "result": _pass(production_loop_undifferentiated),
            "note": "bounded and unbounded loop both come back unknown-node-type from production; the suite fires loop-unbounded only on the bad twin",
        },
    ]
    test_fail = any(t["result"] != "PASS" for t in tests)
    answer_no = not inv["every_construct_has_production_schema_rule_and_conformance_case"]
    return {
        "question": QUESTION,
        "inventory": inv,
        "cases": case_rows,
        "table": table,
        "tests": tests,
        "ok": (not fail) and (not test_fail),
        "answer": {
            "every_construct_has_schema_rule_and_conformance_case_in_production": (
                inv["every_construct_has_production_schema_rule_and_conformance_case"]
            ),
            "every_construct_has_schema_rule_and_conformance_case_in_this_suite": suite_covers,
            "constructs_with_no_production_validator": missing_validator,
            "constructs_with_no_production_schema_rule": inv[
                "constructs_with_no_production_schema_rule"
            ],
            "constructs_with_no_production_conformance_case": inv[
                "constructs_with_no_production_conformance_case"
            ],
            "closed_node_types": inv["closed_node_types"],
            "production_loop_undifferentiated": production_loop_undifferentiated,
            "prose": (
                "No. Production validate_workflow currently closes over "
                f"{inv['closed_node_types']}. Fan-out and barrier have schema "
                "rules (fanout-empty / fanout-unit-unknown, barrier-empty / "
                "barrier-awaits-unknown) and production conformance cases for those "
                "ids. The pre-implementation suite still uses contract ids "
                "fanout-unknown-member and barrier-empty-awaits. "
                + (
                    "Constructs with no production validator at all: "
                    + ", ".join(missing_validator)
                    + ". "
                    if missing_validator
                    else "Every named construct has a production validator. "
                )
                + "repair-loop is a fix-review cycle, not loop-with-convergence; "
                "dispatch retry.py is not a DSL retry node. This suite supplies "
                "schema rules and both-states conformance cases for all seven."
            ),
            "answer_is_no": answer_no or bool(missing_validator),
        },
    }
