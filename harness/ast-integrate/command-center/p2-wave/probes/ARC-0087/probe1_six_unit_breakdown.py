#!/usr/bin/env python3
"""Probe 1: independent contract review + six-unit per-condition breakdown."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from jsonschema import Draft202012Validator  # noqa: E402

from consumer import validate_verdict  # noqa: E402
from evaluator import (  # noqa: E402
    CONDITION_SPEC,
    CONTRACT_PATH,
    MIN_ARTIFACT_BYTES,
    REPO,
    UnitContext,
    context_from_catalog,
    evaluate,
    load_contract,
)

SENTINEL = "SUCCESS:ARC-0087-probe1"
COMPLETED = ("ARC-0003", "ARC-0014", "ARC-0016")
FIX = "command-center/p2-wave/probes/ARC-0087/fixtures"


def incomplete_contexts() -> list[UnitContext]:
    return [
        UnitContext(
            unit_id="FIX-0001",
            unit_class="implementation",
            output_path=f"{FIX}/does-not-exist.json",
            output_schema="command-center/schema/architecture-dossier.schema.json",
            sentinel="SUCCESS:FIX-0001",
            tests_required=["vacuity control: missing artifact must fail condition 2"],
            evidence_requirement="declared evidence anchors",
            reviewer_requirement="independent reviewer",
            exit_code=0,
            process_terminal=True,
            probe_results=[{"id": "probe-vacuity", "command": "true", "exit_code": 0}],
            reviewer_verdict="PASS",
            defects=[],
            manifest_path=f"{FIX}/no-manifest.json",
        ),
        UnitContext(
            unit_id="FIX-0002",
            unit_class="implementation",
            output_path=f"{FIX}/empty.json",
            output_schema="command-center/schema/architecture-dossier.schema.json",
            sentinel="SUCCESS:FIX-0002",
            tests_required=["negative control: empty artifact"],
            evidence_requirement="declared evidence anchors",
            reviewer_requirement="independent reviewer",
            exit_code=0,
            process_terminal=True,
            probe_results=[{"id": "probe-empty", "command": "true", "exit_code": 0}],
            reviewer_verdict="PASS",
            defects=[],
            manifest_path=f"{FIX}/no-manifest.json",
        ),
        UnitContext(
            unit_id="FIX-0003",
            unit_class="implementation",
            output_path=f"{FIX}/no_sentinel.json",
            output_schema=None,
            sentinel="SUCCESS:FIX-0003",
            tests_required=["sentinel presence"],
            evidence_requirement="declared evidence anchors",
            reviewer_requirement="independent reviewer",
            exit_code=0,
            process_terminal=True,
            probe_results=[{"id": "probe-sentinel", "command": "true", "exit_code": 0}],
            reviewer_verdict="PASS",
            defects=[],
            applicability_overrides={"C04": False, "C08": False},
            manifest_path=f"{FIX}/no-manifest.json",
        ),
    ]


def review_contract(contract: dict) -> None:
    Draft202012Validator.check_schema(contract)
    text = json.dumps(contract)
    if "SUCCESS:ARC-0087" not in text:
        raise SystemExit("FAILED: contract text lacks SUCCESS:ARC-0087")
    catalog = contract.get("x-condition-catalog") or []
    ids = [row["id"] for row in catalog]
    want = [cid for cid, _, _ in CONDITION_SPEC]
    if ids != want:
        raise SystemExit(f"FAILED: condition catalog ids {ids} != {want}")
    cond0 = contract["properties"]["conditions"]["prefixItems"][0]
    result_enum = cond0["properties"]["result"]["enum"]
    for token in ("TRUE", "FALSE", "UNKNOWN", "NOT-APPLICABLE"):
        if token not in result_enum:
            raise SystemExit(f"FAILED: result enum missing {token}")
    matrix = contract.get("x-applicability-matrix") or {}
    if "research" not in matrix or matrix["research"].get("C08") is not False:
        raise SystemExit("FAILED: research class must mark C08 not applicable")
    anti = " ".join(contract.get("x-anti-patterns") or []).lower()
    if "exit code zero" not in anti or "digest" not in anti or "path" not in anti:
        raise SystemExit("FAILED: anti-patterns not encoded in contract")
    if (
        contract["properties"]["anti_patterns"]["properties"][
            "exit_code_zero_is_not_success"
        ]["const"]
        is not True
    ):
        raise SystemExit("FAILED: exit-code anti-pattern not const true")
    if MIN_ARTIFACT_BYTES != contract["properties"]["min_artifact_bytes"]["const"]:
        raise SystemExit("FAILED: min_artifact_bytes drift")
    print("independent-review: contract structure PASS")


def cond_map(verdict: dict) -> dict[str, dict]:
    return {c["id"]: c for c in verdict["conditions"]}


def main() -> int:
    if not CONTRACT_PATH.is_file():
        print(f"FAILED: missing {CONTRACT_PATH}")
        return 1
    contract = load_contract()
    review_contract(contract)

    rows: list[tuple[str, dict]] = []
    for uid in COMPLETED:
        ctx = context_from_catalog(uid)
        verdict = evaluate(ctx)
        errs = list(Draft202012Validator(contract).iter_errors(verdict))
        if errs:
            print(json.dumps(verdict, indent=2)[:4000])
            print("FAILED: schema", errs[0].message)
            return 1
        validate_verdict(verdict, contract)
        rows.append(("completed", verdict))

    for ctx in incomplete_contexts():
        verdict = evaluate(ctx)
        errs = list(Draft202012Validator(contract).iter_errors(verdict))
        if errs:
            print(json.dumps(verdict, indent=2)[:4000])
            print("FAILED: schema", errs[0].message)
            return 1
        if verdict["verdict"] == "COMPLETE":
            print(f"FAILED: incomplete fixture {ctx.unit_id} scored COMPLETE")
            return 1
        rows.append(("incomplete", verdict))

    missing = next(v for _k, v in rows if v["unit_id"] == "FIX-0001")
    if cond_map(missing)["C02"]["result"] != "FALSE" or missing["exit_code"] != 0:
        print("FAILED: vacuity — missing artifact did not FALSE C02 under exit 0")
        return 1
    if missing["verdict"] != "INCOMPLETE":
        print("FAILED: vacuity — aggregate was not INCOMPLETE")
        return 1

    empty = next(v for _k, v in rows if v["unit_id"] == "FIX-0002")
    if cond_map(empty)["C03"]["result"] != "FALSE":
        print("FAILED: empty artifact did not FALSE C03")
        return 1

    nosen = next(v for _k, v in rows if v["unit_id"] == "FIX-0003")
    if cond_map(nosen)["C05"]["result"] != "FALSE":
        print("FAILED: missing sentinel did not FALSE C05")
        return 1
    if cond_map(nosen)["C04"]["result"] != "NOT-APPLICABLE":
        print("FAILED: C04 override was not NOT-APPLICABLE")
        return 1
    counted = sum(
        1 for c in nosen["conditions"] if c["applicable"] and c["result"] == "TRUE"
    )
    if nosen["applicable_pass_count"] != counted:
        print("FAILED: applicable_pass_count counted N/A as pass")
        return 1

    print(
        "kind unit_id verdict C01 C02 C03 C04 C05 C06 C07 C08 C09 C10 C11 C12 pass fail unk na"
    )
    for kind, verdict in rows:
        cm = cond_map(verdict)
        bits = " ".join(cm[cid]["result"][0] for cid, _, _ in CONDITION_SPEC)
        print(
            f"{kind} {verdict['unit_id']} {verdict['verdict']} {bits} "
            f"{verdict['applicable_pass_count']} {verdict['applicable_fail_count']} "
            f"{verdict['applicable_unknown_count']} {verdict['not_applicable_count']}"
        )
    out = HERE / "six-unit-breakdown.json"
    out.write_text(
        json.dumps(
            {
                "predicate": str(CONTRACT_PATH.relative_to(REPO)),
                "rows": [{"kind": kind, "verdict": verdict} for kind, verdict in rows],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"published {out.relative_to(REPO)}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
