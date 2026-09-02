#!/usr/bin/env python3
"""Probe 2: both-states + production gap + overclaim mutant. Independent of probe 1."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import cases as C  # noqa: E402
import contract_validator as CV  # noqa: E402
import inventory as INV  # noqa: E402
import production as P  # noqa: E402
from constructs import ORDER  # noqa: E402

ART = REPO / "command-center/receipts/TST-0037.json"
SCHEMA = REPO / "command-center/schema/conformance-report.schema.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0037-probe2 {msg}")
    return 1


def main() -> int:
    # Contract both-states derived from fixtures, not from the artifact conclusion.
    per: dict[str, dict[str, bool]] = {cid: {"good": False, "bad": False} for cid in ORDER}
    for spec in C.materialize():
        ids = CV.ids_of(spec["doc"])
        if spec["role"] == "good":
            ok = ids == set()
        else:
            ok = set(spec["expect_contract"]) <= ids
        per[spec["construct"]][spec["role"]] = ok
        print(
            f"contract {spec['id']} ids={sorted(ids)} expect={sorted(spec['expect_contract'])} ok={ok}"
        )
        if not ok:
            return fail(f"contract both-states {spec['id']}")
    if not all(v["good"] and v["bad"] for v in per.values()):
        return fail(f"missing both-states {per}")

    # Production: fan-out/barrier discriminate; loop does not.
    good = C.good_fanout_barrier()
    empty_fo = C.neg_fanout_empty()
    good_ids = P.ids_of(REPO, good)
    empty_ids = P.ids_of(REPO, empty_fo)
    print(f"production good={sorted(good_ids)} empty_fanout={sorted(empty_ids)}")
    if good_ids:
        return fail(f"production good fanout/barrier not clean {sorted(good_ids)}")
    if "fanout-empty" not in empty_ids:
        return fail("production empty fanout did not fire fanout-empty")

    loop_g = P.ids_of(REPO, C.good_loop())
    loop_b = P.ids_of(REPO, C.neg_loop_unbounded())
    print(f"production loop good={sorted(loop_g)} unbounded={sorted(loop_b)}")
    if "unknown-node-type" not in loop_g or "unknown-node-type" not in loop_b:
        return fail("production loop was not unknown-node-type")
    if "loop-unbounded" in loop_g or "loop-unbounded" in loop_b:
        return fail("production unexpectedly emits loop-unbounded")
    if CV.ids_of(C.good_loop()):
        return fail("contract rejected bounded loop")
    if "loop-unbounded" not in CV.ids_of(C.neg_loop_unbounded()):
        return fail("contract did not fire loop-unbounded")

    inv = INV.scan(REPO)
    missing = list(inv["constructs_with_no_production_validator"])
    for cid in (
        "loop-with-convergence",
        "human-checkpoint",
        "subworkflow",
        "retry",
        "resume",
    ):
        if cid not in missing:
            # Live tree grew a validator — still require it to appear in CLOSED_NODE_TYPES.
            row = next(r for r in inv["rows"] if r["construct"] == cid)
            if not row["production_validator"]:
                return fail(f"{cid} missing from no-validator list without a closed type")
    print(f"missing_validators={missing} closed={inv['closed_node_types']}")

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    for garbage in ({}, {"totally": "unrelated", "passing_tests": 999999}, {"x": "x" * 200}):
        if not list(validator.iter_errors(garbage)):
            return fail(f"output schema accepted garbage {list(garbage)[:1]}")

    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    aerrs = list(validator.iter_errors(doc))
    if aerrs:
        return fail(f"artifact schema {aerrs[0].message}")
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:TST-0037" not in ART.read_text(encoding="utf-8"):
        return fail("sentinel absent")

    rec_missing = list(
        (doc.get("answer") or {}).get("constructs_with_no_production_validator") or []
    )
    if rec_missing != missing:
        return fail(f"artifact missing list {rec_missing} != live {missing}")

    mutant = copy.deepcopy(doc)
    mutant["answer"]["every_construct_has_schema_rule_and_conformance_case_in_production"] = True
    mutant["answer"]["constructs_with_no_production_validator"] = []
    mutant["answer"]["answer_is_no"] = False
    for row in mutant.get("construct_table") or []:
        row["production_validator"] = True
        row["schema_rule"] = True
    overclaim = (
        mutant["answer"]["constructs_with_no_production_validator"] != missing
        or mutant["answer"]["every_construct_has_schema_rule_and_conformance_case_in_production"]
        is True
        and missing
    )
    print(f"overclaim_mutant_detected={bool(overclaim)} live_missing={missing}")
    if not overclaim:
        return fail("overclaim mutant was not distinguishable")
    if (doc.get("answer") or {}).get(
        "every_construct_has_schema_rule_and_conformance_case_in_production"
    ) is True and missing:
        return fail("artifact overclaims production coverage")

    print("SUCCESS:TST-0037-probe2 both-states production-gap overclaim-mutant")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
