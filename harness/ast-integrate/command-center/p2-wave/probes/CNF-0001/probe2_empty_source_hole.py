#!/usr/bin/env python3
"""Named probe 2: in-process empty-source hole + schema merit.

Mechanically different from probe 1: does not read the hand-built fixture
files and does not spawn the CLI. Builds the CONFIRMED+empty-source shape
in memory, runs validate_receipt() as a library, and independently asks
jsonschema whether that instance is valid under the on-disk schema.
Both instruments must answer NO. A well-formed receipt must pass (both
states). Garbage documents must be rejected so the schema is non-vacuous.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_DIR = REPO / "command-center" / "schema"
sys.path.insert(0, str(SCHEMA_DIR))

import validate_confirmation_receipt as V  # noqa: E402


SENTINEL = (
    "SUCCESS:CNF-0001 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and all six negative fixtures "
    "exited non-zero and the positive fixture exited zero in the same invocation. "
    "Any other terminal state is FAILED:CNF-0001 <classification> with the "
    "diagnostic tail attached."
)
GARBAGE = (
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
    {},
)


def complete_receipt() -> dict:
    # Built here, not loaded from fixtures/, so this probe is not a re-read
    # of probe 1's files.
    return {
        "claim_id": "CNF-0001-P2-LIVE",
        "confirmer": {"id": "probe2-in-process-confirmer", "vendor": "anthropic"},
        "source_probe": {
            "tool": "jsonschema",
            "shell": "python-import",
            "field": "iter_errors",
            "kind": "in-process-library",
        },
        "verifier_probe": {
            "tool": "validate_receipt",
            "shell": "python-import",
            "field": "semantic_violations",
            "kind": "named-rule-scan",
        },
        "verbatim_probe_output": "in-process CONFIRMED+empty-source ok=false; complete ok=true",
        "verdict": "CONFIRMED",
        "residual": "none — library and jsonschema both reject the empty source",
    }


def rules_of(report: dict) -> set[str]:
    return {v["rule"] for v in report.get("violations") or []}


def schema_accepts(schema: dict, instance: object) -> bool:
    import jsonschema

    return not list(jsonschema.Draft202012Validator(schema).iter_errors(instance))


def main() -> int:
    receipt_schema_path = SCHEMA_DIR / "confirmation-receipt.schema.json"
    discrepancy_schema_path = SCHEMA_DIR / "discrepancy-record.schema.json"
    print(f"receipt_schema_abs={receipt_schema_path.resolve()}")
    print(f"discrepancy_schema_abs={discrepancy_schema_path.resolve()}")
    if not receipt_schema_path.is_file() or not discrepancy_schema_path.is_file():
        print("FAILED:CNF-0001-probe2 a required schema file is absent")
        return 1
    if receipt_schema_path.resolve() != V.SCHEMA_PATH.resolve():
        print("FAILED:CNF-0001-probe2 validator SCHEMA_PATH mismatch")
        return 1

    receipt_schema = json.loads(receipt_schema_path.read_text(encoding="utf-8"))
    discrepancy_schema = json.loads(discrepancy_schema_path.read_text(encoding="utf-8"))
    if SENTINEL not in json.dumps(receipt_schema):
        print("FAILED:CNF-0001-probe2 sentinel absent from receipt schema")
        return 1

    import jsonschema

    jsonschema.Draft202012Validator.check_schema(receipt_schema)
    jsonschema.Draft202012Validator.check_schema(discrepancy_schema)
    print("check_schema=ok both schemas")

    for i, probe in enumerate(GARBAGE):
        if schema_accepts(receipt_schema, probe):
            print(f"FAILED:CNF-0001-probe2 receipt schema accepts garbage[{i}]")
            return 1
        if schema_accepts(discrepancy_schema, probe):
            print(f"FAILED:CNF-0001-probe2 discrepancy schema accepts garbage[{i}]")
            return 1
    print("garbage_rejected=3/3 both schemas")

    good = complete_receipt()
    good_report = V.validate_receipt(good, receipt_schema)
    print(f"complete_library_ok={good_report['ok']} rules={good_report['rules']}")
    if not good_report["ok"]:
        print(json.dumps(good_report, indent=2)[:2000])
        print("FAILED:CNF-0001-probe2 well-formed receipt rejected (false positive)")
        return 1
    if not schema_accepts(receipt_schema, good):
        print("FAILED:CNF-0001-probe2 jsonschema rejects well-formed receipt")
        return 1

    hole = complete_receipt()
    hole["source_probe"] = ""
    hole_report = V.validate_receipt(hole, receipt_schema)
    hole_schema_ok = schema_accepts(receipt_schema, hole)
    print(
        "question=does a receipt with verdict=CONFIRMED and an EMPTY source_probe pass?"
    )
    print(
        f"answer=NO library_ok={hole_report['ok']} library_exit={hole_report['exit_code']} "
        f"jsonschema_accepts={hole_schema_ok} rules={hole_report['rules']}"
    )
    if hole_report["ok"] or hole_report["exit_code"] == 0:
        print("FAILED:CNF-0001-probe2 empty-source CONFIRMED passed the library")
        return 1
    if "empty-source" not in rules_of(hole_report):
        print("FAILED:CNF-0001-probe2 empty-source rule not named on the hole")
        return 1
    if hole_schema_ok:
        print("FAILED:CNF-0001-probe2 jsonschema accepted CONFIRMED+empty source_probe")
        return 1

    twin = complete_receipt()
    twin["verifier_probe"] = dict(twin["source_probe"])
    twin_report = V.validate_receipt(twin, receipt_schema)
    twin_schema_ok = schema_accepts(receipt_schema, twin)
    print(
        f"same_probe library_ok={twin_report['ok']} jsonschema_accepts={twin_schema_ok} "
        f"rules={twin_report['rules']}"
    )
    if twin_report["ok"] or "same-probe-rerun" not in rules_of(twin_report):
        print("FAILED:CNF-0001-probe2 identical fingerprints were not same-probe-rerun")
        return 1
    # JSON Schema cannot compare two instance locations. If it rejected this
    # shape it would be for some other reason; the CLI must still be the
    # instrument that names same-probe-rerun.
    if not twin_schema_ok:
        print(
            "NOTE: jsonschema also rejected the identical-fingerprint pair; "
            "same-probe-rerun is still required from the library"
        )

    # Both-states for the empty-source detector: the detector is silent in
    # neither state (fires on the hole, silent on the complete receipt).
    if hole_report["ok"] == good_report["ok"]:
        print("FAILED:CNF-0001-probe2 empty-source detector silent in both states")
        return 1

    print("SUCCESS:CNF-0001-probe2 empty-source hole closed; same-probe-rerun named")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
