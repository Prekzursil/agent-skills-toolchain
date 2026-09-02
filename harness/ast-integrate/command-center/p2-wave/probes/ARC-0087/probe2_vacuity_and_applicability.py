#!/usr/bin/env python3
"""Probe 2: vacuity (C02 FALSE on missing artifact) + applicability honesty + consumer call site."""
from __future__ import annotations

import copy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from jsonschema import Draft202012Validator  # noqa: E402

from consumer import validate_verdict  # noqa: E402
from evaluator import CONDITION_SPEC, UnitContext, evaluate, load_contract  # noqa: E402

SENTINEL = "SUCCESS:ARC-0087-probe2"
FIX = "command-center/p2-wave/probes/ARC-0087/fixtures"


def missing_ctx() -> UnitContext:
    return UnitContext(
        unit_id="FIX-0001",
        unit_class="implementation",
        output_path=f"{FIX}/does-not-exist.json",
        output_schema="command-center/schema/architecture-dossier.schema.json",
        sentinel="SUCCESS:FIX-0001",
        tests_required=["vacuity control: missing artifact"],
        evidence_requirement="anchors",
        reviewer_requirement="independent reviewer",
        exit_code=0,
        process_terminal=True,
        probe_results=[{"id": "vacuity-negative", "command": "true", "exit_code": 0}],
        reviewer_verdict="PASS",
        defects=[],
        manifest_path=f"{FIX}/no-manifest.json",
    )


def research_ctx() -> UnitContext:
    return UnitContext(
        unit_id="RES-0001",
        unit_class="research",
        output_path=f"{FIX}/research_note.json",
        output_schema=None,
        sentinel="SUCCESS:RES-0001",
        tests_required=["literature comparison"],
        evidence_requirement="source lineage",
        reviewer_requirement="independent reviewer",
        exit_code=0,
        process_terminal=True,
        probe_results=[{"id": "probe-read", "command": "true", "exit_code": 0}],
        reviewer_verdict="PASS",
        defects=[],
        manifest_path=f"{FIX}/no-manifest.json",
    )


def main() -> int:
    contract = load_contract()
    Draft202012Validator.check_schema(contract)

    missing = evaluate(missing_ctx())
    c02 = next(c for c in missing["conditions"] if c["id"] == "C02")
    if missing["exit_code"] != 0:
        print("FAILED: fixture exit_code was not 0")
        return 1
    if c02["result"] != "FALSE":
        print(f"FAILED: vacuity C02={c02['result']} (want FALSE) reason={c02['reason']}")
        return 1
    if missing["verdict"] == "COMPLETE":
        print("FAILED: exit 0 + missing artifact produced COMPLETE")
        return 1
    validate_verdict(missing, contract)
    print(
        f"vacuity: exit_code=0 C02={c02['result']} verdict={missing['verdict']} "
        "(COMPLETE forbidden)"
    )

    research = evaluate(research_ctx())
    c08 = next(c for c in research["conditions"] if c["id"] == "C08")
    if c08["applicable"] is not False or c08["result"] != "NOT-APPLICABLE":
        print(
            f"FAILED: research C08 applicable={c08['applicable']} result={c08['result']}"
        )
        return 1
    true_ids = [
        c["id"]
        for c in research["conditions"]
        if c["applicable"] and c["result"] == "TRUE"
    ]
    if "C08" in true_ids:
        print("FAILED: C08 N/A was counted as a pass")
        return 1
    if research["applicable_pass_count"] != len(true_ids):
        print("FAILED: applicable_pass_count includes N/A")
        return 1
    if research["not_applicable_count"] < 1:
        print("FAILED: not_applicable_count did not record C08")
        return 1
    validate_verdict(research, contract)
    print(
        f"applicability: C08 result={c08['result']} counted_as_pass=False "
        f"pass_count={research['applicable_pass_count']} na={research['not_applicable_count']}"
    )

    mutant = copy.deepcopy(research)
    for cond in mutant["conditions"]:
        if cond["id"] == "C08":
            cond["applicable"] = False
            cond["result"] = "TRUE"
            cond["reason"] = "dishonest N/A counted as pass"
    mutant_errs = list(Draft202012Validator(contract).iter_errors(mutant))
    if not mutant_errs:
        print("FAILED: schema accepted N/A condition with result TRUE")
        return 1
    print(f"schema-rejects-NA-as-TRUE: {mutant_errs[0].message}")

    garbage = [
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {},
    ]
    for item in garbage:
        errs = list(Draft202012Validator(contract).iter_errors(item))
        if not errs:
            print(f"FAILED: contract is vacuous on {list(item)[:1]}")
            return 1
    print("garbage-rejected: 3/3")
    validate_verdict(missing, contract)
    validate_verdict(research, contract)
    print(
        "consumer-call-site: "
        "command-center/p2-wave/probes/ARC-0087/consumer.py::validate_verdict"
    )
    print(f"conditions_wired={len(CONDITION_SPEC)}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
