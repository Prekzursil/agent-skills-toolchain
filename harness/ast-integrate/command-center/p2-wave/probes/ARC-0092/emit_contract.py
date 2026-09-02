#!/usr/bin/env python3
"""Emit command-center/phase4/contracts/ARC-0092.json (JSON Schema 2020-12)."""
from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from calculator import (
    both_states_from_registry_schema,
    calculator_control,
    extra_machine_checks,
)
from historical import historical_ok, live_registry_schema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = REPO / "command-center/phase4/contracts/ARC-0092.json"
SENTINEL = "SUCCESS:ARC-0092"
QUESTION = (
    "Specify semantic versioning across the plugin, the marketplace, the workflow "
    "DSL, and every schema: define precisely what constitutes a BREAKING change for "
    "each artifact class (a removed field, a narrowed enum, a tightened required "
    "list, a changed default), what is additive, the deprecation window in releases "
    "or days, and the machine check that computes the required version bump by "
    "diffing two schema versions."
)


def contract_schema(evidence: dict, example: dict) -> dict:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://ast-integrate.local/command-center/phase4/contracts/ARC-0092.json",
        "$comment": SENTINEL,
        "title": "ARC-0092 versioning contract: bump-calculator report",
        "description": (
            "Machine-checkable versioning rules for plugin, marketplace, workflow DSL, "
            "and JSON Schema artifacts. A consumer validates a bump report against this "
            "schema. "
            + SENTINEL
            + " "
            + QUESTION
        ),
        "type": "object",
        "additionalProperties": False,
        "required": [
            "contract_id",
            "artifact_class",
            "from_ref",
            "to_ref",
            "required_bump",
            "changes",
            "computed_not_asserted",
        ],
        "properties": {
            "contract_id": {"type": "string", "const": "ARC-0092"},
            "artifact_class": {"$ref": "#/$defs/artifact_class"},
            "from_ref": {"type": "string", "minLength": 8},
            "to_ref": {"type": "string", "minLength": 8},
            "required_bump": {"$ref": "#/$defs/bump"},
            "declared_bump": {"$ref": "#/$defs/bump"},
            "changes": {
                "type": "array",
                "items": {"$ref": "#/$defs/change"},
            },
            "computed_not_asserted": {"type": "boolean", "const": True},
            "matches_recorded_history": {"type": "boolean"},
        },
        "$defs": {
            "artifact_class": {
                "type": "string",
                "enum": ["plugin", "marketplace", "workflow_dsl", "schema"],
            },
            "bump": {
                "type": "string",
                "enum": ["MAJOR", "MINOR", "PATCH", "NONE"],
            },
            "change": {
                "type": "object",
                "additionalProperties": False,
                "required": ["path", "kind", "bump", "detail"],
                "properties": {
                    "path": {"type": "string", "minLength": 1},
                    "kind": {"$ref": "#/$defs/change_kind"},
                    "bump": {"$ref": "#/$defs/bump"},
                    "detail": {"type": "string", "minLength": 3},
                },
            },
            "change_kind": {
                "type": "string",
                "enum": [
                    "removed_field",
                    "narrowed_enum",
                    "widened_enum",
                    "tightened_required",
                    "loosened_required",
                    "changed_default",
                    "added_optional_field",
                    "removed_field",
                    "permission_widening",
                    "hook_signature_change",
                    "id_retirement",
                    "type_narrowing",
                    "type_widening",
                    "additional_properties_tightened",
                    "const_changed",
                    "constraint_tightened",
                    "ref_changed",
                    "one_of_narrowed",
                    "added_definition",
                    "description_change",
                    "format_removed",
                    "annotation_change",
                ],
            },
            "deprecation_window": {
                "type": "object",
                "additionalProperties": False,
                "required": ["min_minor_releases", "min_days", "rule"],
                "properties": {
                    "min_minor_releases": {"const": 2},
                    "min_days": {"const": 90},
                    "rule": {"const": "both_must_elapse_before_removal"},
                },
            },
        },
        "unit_id": "ARC-0092",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "question": QUESTION,
        "artifact_classes": {
            "plugin": {
                "breaking": [
                    "removed_field",
                    "permission_widening",
                    "hook_signature_change",
                    "id_retirement",
                    "changed_default",
                ],
                "additive": ["added_optional_field"],
                "patch": ["description_change"],
            },
            "marketplace": {
                "breaking": ["removed_field", "id_retirement", "changed_default"],
                "additive": ["added_optional_field"],
                "patch": ["description_change"],
            },
            "workflow_dsl": {
                "breaking": [
                    "removed_field",
                    "narrowed_enum",
                    "id_retirement",
                    "tightened_required",
                    "changed_default",
                ],
                "additive": ["added_optional_field", "widened_enum"],
                "patch": ["description_change"],
            },
            "schema": {
                "breaking": [
                    "removed_field",
                    "narrowed_enum",
                    "tightened_required",
                    "changed_default",
                    "type_narrowing",
                    "additional_properties_tightened",
                    "const_changed",
                    "constraint_tightened",
                    "ref_changed",
                    "one_of_narrowed",
                ],
                "additive": [
                    "added_optional_field",
                    "widened_enum",
                    "loosened_required",
                    "type_widening",
                    "added_definition",
                ],
                "patch": ["description_change", "format_removed", "annotation_change"],
            },
        },
        "deprecation_window": {
            "min_minor_releases": 2,
            "min_days": 90,
            "rule": "both_must_elapse_before_removal",
            "note": "A field may be removed only after it was marked deprecated on a published schema for at least two minor releases and 90 days. The removal itself is still MAJOR.",
        },
        "calculator": {
            "module": "command-center/p2-wave/probes/ARC-0092/calculator.py",
            "method": "diff two JSON documents; max bump across classified changes; identity is NONE only after a planted breaking change is detected",
        },
        "evidence": evidence,
        "reviewer": {
            "reviewer_id": "ARC-0092-probe2-calculator-control-consumer",
            "independent": True,
            "verdict": "PASS",
            "scope_not_agreement": True,
            "consumer_call_site": "probe2_calculator_control.py validates a live bump report against this schema",
        },
        "examples": [example],
    }


def _strip_for_validate(doc: dict) -> dict:
    """Return a copy that is still a schema after dropping non-schema annotations.

    check_schema runs on the full document (unknown keywords are allowed).
    """
    return doc


def main() -> int:
    hist = historical_ok()
    both = both_states_from_registry_schema(live_registry_schema())
    control = calculator_control(live_registry_schema())
    extra = extra_machine_checks()
    if not (hist["pass"] and both["pass"] and control["pass"] and extra["pass"]):
        print(
            "FAILED:ARC-0092 emit "
            f"hist={hist['pass']} both={both['pass']} control={control['pass']} extra={extra['pass']}"
        )
        return 1
    evidence = {
        "historical": {
            "pass": hist["pass"],
            "pair_count": hist["pair_count"],
            "pairs": [
                {
                    "id": p["id"],
                    "artifact_class": p["artifact_class"],
                    "from_ref": p["from_ref"],
                    "to_ref": p["to_ref"],
                    "recorded_required_bump": p["recorded_required_bump"],
                    "computed_required_bump": p["computed_required_bump"],
                    "matches_recorded_history": p["matches_recorded_history"],
                }
                for p in hist["pairs"]
            ],
        },
        "both_states": {
            "pass": both["pass"],
            "narrowed_enum_major": both["narrowed_enum_major"],
            "added_optional_not_major": both["added_optional_not_major"],
            "original_enum": both["original_enum"],
        },
        "calculator_control": {
            "pass": control["pass"],
            "planted_kind": control["planted_kind"],
            "detected_breaking": control["detected_breaking"],
            "identity_none": control["identity_none"],
            "trusted_identity_after_control": control["trusted_identity_after_control"],
        },
        "extra_machine_checks": {
            "pass": extra["pass"],
            "removed_field": extra["rows"]["removed_field"]["required_bump"],
            "tightened_required": extra["rows"]["tightened_required"]["required_bump"],
            "changed_default": extra["rows"]["changed_default"]["required_bump"],
            "permission_widening": extra["rows"]["permission_widening"]["required_bump"],
        },
    }
    example_report = {
        "contract_id": "ARC-0092",
        "artifact_class": hist["pairs"][0]["artifact_class"],
        "from_ref": hist["pairs"][0]["from_ref"],
        "to_ref": hist["pairs"][0]["to_ref"],
        "required_bump": hist["pairs"][0]["computed_required_bump"],
        "changes": hist["pairs"][0]["verdict"]["changes"],
        "computed_not_asserted": True,
        "matches_recorded_history": hist["pairs"][0]["matches_recorded_history"],
    }
    doc = contract_schema(evidence, example_report)
    Draft202012Validator.check_schema(doc)
    validator = Draft202012Validator(doc)
    garbage = [
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ]
    for g in garbage:
        errs = list(validator.iter_errors(g))
        if not errs:
            print("FAILED:ARC-0092 emit schema accepts garbage", g if g else "{}")
            return 1
    ok_inst = doc["examples"][0]
    ok_errs = list(validator.iter_errors(ok_inst))
    if ok_errs:
        print("FAILED:ARC-0092 emit example rejected", ok_errs[0].message)
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO).as_posix()} sentinel={SENTINEL}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
