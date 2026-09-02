#!/usr/bin/env python3
"""Probe 2: both-states controls on applicability promotion and schema.

Gold facts stay green. Known-broken mutants must go red:
  * drop every baseline on SWE-bench -> E3 cannot promote, row inapplicable
  * strip the named improvement from SWE-bench -> inapplicable
  * drop all inapplicable rows -> popular-control fails
  * dishonest HumanEval-applicable row with empty improvement -> schema reject
  * three garbage documents -> schema reject
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import jsonschema
from jsonschema.exceptions import ValidationError

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402

ART = REPO / "command-center/research/RES-0093.json"
SCHEMA = REPO / "command-center/schema/research-registry.schema.json"
GARBAGE = [
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"x": "x" * 2000},
]


def fail(msg: str) -> int:
    print(f"FAILED:RES-0093-probe2 {msg}")
    return 1


def row_by(rows: list[dict], bid: str) -> dict:
    for r in rows:
        if r["benchmark_id"] == bid:
            return r
    raise KeyError(bid)


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    stored = json.loads(ART.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.validate(stored, schema)

    facts = E.load_facts()
    gold_rows = E.build_register(facts)
    gold_tests = E.tests_from_register(gold_rows)
    if gold_tests["named_improvement_per_applicable"] is not True:
        return fail("gold named-improvement predicate false")
    if gold_tests["inapplicable_popular_control"]["pass"] is not True:
        return fail("gold popular inapplicable control false")
    if row_by(gold_rows, "humaneval")["applicability_verdict"] != "inapplicable":
        return fail("gold HumanEval not inapplicable")
    if row_by(gold_rows, "swe-bench")["applicability_verdict"] != "applicable":
        return fail("gold SWE-bench not applicable")

    dropped = E.build_register(E.mutate_drop_all_baselines(facts, "swe-bench"))
    swe_dropped = row_by(dropped, "swe-bench")
    if swe_dropped["applicability_verdict"] != "inapplicable":
        return fail("E3-without-baseline still promoted SWE-bench")
    if swe_dropped["promoting_claim_ids"]:
        return fail("E3 claims listed as promoting")
    if not all(c["evidence_tier"] == "E3" for c in swe_dropped["citations"]):
        return fail("dropped-baseline claims were not all E3")

    stripped = E.build_register(E.mutate_strip_improvement(facts, "swe-bench"))
    if row_by(stripped, "swe-bench")["applicability_verdict"] != "inapplicable":
        return fail("SWE-bench stayed applicable with no named improvement")
    if row_by(stripped, "swe-bench")["named_detectable_improvement"] is not None:
        return fail("stripped improvement still named")

    no_ctrl = E.tests_from_register(E.build_register(E.mutate_drop_inapplicable(facts)))
    if no_ctrl["inapplicable_popular_control"]["pass"] is not False:
        return fail("dropping inapplicable rows did not trip the popular control")
    if no_ctrl["inapplicable_count"] != 0:
        return fail("expected zero inapplicable after drop")

    dishonest = copy.deepcopy(stored)
    for row in dishonest["benchmark_register"]:
        if row["benchmark_id"] == "humaneval":
            row["applicability_verdict"] = "applicable"
            row["named_detectable_improvement"] = ""
            break
    try:
        jsonschema.validate(dishonest, schema)
    except ValidationError:
        schema_caught_empty_improvement = True
    else:
        return fail("schema accepted HumanEval applicable with empty improvement")

    rejected = 0
    for g in GARBAGE:
        try:
            jsonschema.validate(g, schema)
        except ValidationError:
            rejected += 1
        else:
            return fail(f"schema accepted garbage {list(g)[:2]}")
    if rejected != 3:
        return fail(f"garbage rejected {rejected}/3")

    verbatim = None
    for r in gold_rows:
        for c in r["citations"]:
            if c["claim_id"] == "swev-verbatim-gold":
                verbatim = c
    if verbatim is None or verbatim["evidence_tier"] != "E3":
        return fail("verbatim-gold claim is not E3")
    owner = row_by(gold_rows, "swe-bench-verified-public")
    if "swev-verbatim-gold" in (owner.get("promoting_claim_ids") or []):
        return fail("E3 verbatim-gold promoted Verified")
    if owner["applicability_verdict"] != "inapplicable":
        return fail("public SWE-bench Verified was marked applicable")

    print(
        json.dumps(
            {
                "gold_applicable": gold_tests["applicable_count"],
                "e3_drop_baseline_inapplicable": True,
                "strip_improvement_inapplicable": True,
                "popular_control_both_states": True,
                "schema_caught_empty_improvement": schema_caught_empty_improvement,
                "garbage_rejected": rejected,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print(
        "gold_ok E3-cannot-promote strip-improvement popular-control "
        f"schema-if-then garbage={rejected}/3"
    )
    print("SUCCESS:RES-0093-probe2 controls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
