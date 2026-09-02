#!/usr/bin/env python3
"""Emit command-center/phase4/contracts/ARC-0087.json — the completion-verdict schema."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from evaluator import (  # noqa: E402
    APPLICABILITY_MATRIX,
    CONDITION_SPEC,
    CONTRACT_PATH,
    MIN_ARTIFACT_BYTES,
    PREDICATE_ID,
    UNIT_CLASSES,
)

SENTINEL = "SUCCESS:ARC-0087"
SPEC_LINES = (
    "A unit is complete only when all applicable conditions hold:\n"
    "1. process/task reached a valid terminal state;\n"
    "2. expected artifact exists;\n"
    "3. artifact is non-empty and exceeds a meaningful minimum size;\n"
    "4. artifact parses against its schema;\n"
    "5. required sentinel is present;\n"
    "6. required evidence anchors exist;\n"
    "7. required tests ran and passed;\n"
    "8. negative controls or mutations fail as expected;\n"
    "9. independent reviewer status is PASS;\n"
    "10. no unresolved P0/P1 defect is attached;\n"
    "11. output was registered in the artifact manifest;\n"
    "12. downstream consumers can read it.\n"
    "Exit code zero alone is never success. A plausible digest is not a receipt. "
    "A file path in text is not proof the file exists."
)


def condition_prefix_items() -> list[dict]:
    items = []
    for cid, number, name in CONDITION_SPEC:
        items.append(
            {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "id",
                    "number",
                    "name",
                    "applicable",
                    "result",
                    "evidence_pointer",
                    "reason",
                ],
                "properties": {
                    "id": {"type": "string", "const": cid},
                    "number": {"type": "integer", "const": number},
                    "name": {"type": "string", "const": name},
                    "applicable": {"type": "boolean"},
                    "result": {
                        "type": "string",
                        "enum": ["TRUE", "FALSE", "UNKNOWN", "NOT-APPLICABLE"],
                    },
                    "evidence_pointer": {"type": "string", "minLength": 1},
                    "reason": {"type": "string", "minLength": 1},
                },
                "allOf": [
                    {
                        "if": {
                            "properties": {"applicable": {"const": False}},
                            "required": ["applicable"],
                        },
                        "then": {
                            "properties": {"result": {"const": "NOT-APPLICABLE"}},
                        },
                        "else": {
                            "properties": {
                                "result": {
                                    "type": "string",
                                    "enum": ["TRUE", "FALSE", "UNKNOWN"],
                                }
                            }
                        },
                    }
                ],
            }
        )
    return items


def build_schema() -> dict:
    prefix = condition_prefix_items()
    matrix = {
        cls: {cid: bool(flags[cid]) for cid, _, _ in CONDITION_SPEC}
        for cls, flags in APPLICABILITY_MATRIX.items()
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://ast-integrate.local/command-center/phase4/contracts/ARC-0087.json",
        "title": "ARC-0087 shared completion-predicate verdict",
        "description": (
            f"{SENTINEL}. Formal contract for the shared 12-condition completion "
            "predicate: typed per-condition results, per-unit-class applicability, "
            "UNKNOWN distinct from FALSE, NOT-APPLICABLE never counted as a pass, "
            "and exit code 0 structurally incapable of COMPLETE. "
            + SPEC_LINES
        ),
        "$comment": (
            f"{SENTINEL} predicate_id={PREDICATE_ID} min_artifact_bytes="
            f"{MIN_ARTIFACT_BYTES}. Callers MUST emit the per-condition array, "
            "never a lone boolean. applicable_pass_count counts only result=TRUE "
            "on applicable conditions."
        ),
        "type": "object",
        "additionalProperties": False,
        "required": [
            "predicate_id",
            "schema_id",
            "unit_id",
            "unit_class",
            "verdict",
            "exit_code",
            "evaluated_from_exit_code_alone",
            "min_artifact_bytes",
            "applicable_pass_count",
            "applicable_fail_count",
            "applicable_unknown_count",
            "not_applicable_count",
            "anti_patterns",
            "conditions",
        ],
        "properties": {
            "predicate_id": {"type": "string", "const": PREDICATE_ID},
            "schema_id": {
                "type": "string",
                "const": "command-center/phase4/contracts/ARC-0087.json",
            },
            "unit_id": {
                "type": "string",
                "minLength": 6,
                "pattern": "^[A-Z]{2,5}-[0-9]{4}$",
            },
            "unit_class": {"type": "string", "enum": list(UNIT_CLASSES)},
            "verdict": {
                "type": "string",
                "enum": ["COMPLETE", "INCOMPLETE", "UNKNOWN"],
                "description": (
                    "COMPLETE iff every applicable condition is TRUE. INCOMPLETE if "
                    "any applicable condition is FALSE. UNKNOWN if no applicable "
                    "FALSE and at least one applicable UNKNOWN. NOT-APPLICABLE rows "
                    "never decide the aggregate."
                ),
            },
            "exit_code": {"type": ["integer", "null"]},
            "evaluated_from_exit_code_alone": {
                "type": "boolean",
                "description": "Must be false. Exit 0 is never a completion proof.",
            },
            "min_artifact_bytes": {
                "type": "integer",
                "const": MIN_ARTIFACT_BYTES,
            },
            "applicable_pass_count": {"type": "integer", "minimum": 0, "maximum": 12},
            "applicable_fail_count": {"type": "integer", "minimum": 0, "maximum": 12},
            "applicable_unknown_count": {"type": "integer", "minimum": 0, "maximum": 12},
            "not_applicable_count": {"type": "integer", "minimum": 0, "maximum": 12},
            "anti_patterns": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "exit_code_zero_is_not_success",
                    "plausible_digest_is_not_receipt",
                    "path_in_text_is_not_existence",
                ],
                "properties": {
                    "exit_code_zero_is_not_success": {"type": "boolean", "const": True},
                    "plausible_digest_is_not_receipt": {"type": "boolean", "const": True},
                    "path_in_text_is_not_existence": {"type": "boolean", "const": True},
                },
            },
            "conditions": {
                "type": "array",
                "minItems": 12,
                "maxItems": 12,
                "prefixItems": prefix,
                "items": False,
            },
        },
        "allOf": [
            {
                "if": {
                    "properties": {"verdict": {"const": "COMPLETE"}},
                    "required": ["verdict"],
                },
                "then": {
                    "properties": {
                        "evaluated_from_exit_code_alone": {"const": False},
                        "applicable_fail_count": {"const": 0},
                        "applicable_unknown_count": {"const": 0},
                        "conditions": {
                            "type": "array",
                            "items": {
                                "not": {
                                    "type": "object",
                                    "properties": {
                                        "applicable": {"const": True},
                                        "result": {"enum": ["FALSE", "UNKNOWN"]},
                                    },
                                    "required": ["applicable", "result"],
                                }
                            },
                        },
                    }
                },
            },
            {
                "if": {
                    "properties": {
                        "conditions": {
                            "contains": {
                                "type": "object",
                                "properties": {
                                    "applicable": {"const": True},
                                    "result": {"const": "FALSE"},
                                },
                                "required": ["applicable", "result"],
                            }
                        }
                    }
                },
                "then": {"properties": {"verdict": {"const": "INCOMPLETE"}}},
            },
            {
                "if": {
                    "allOf": [
                        {
                            "properties": {
                                "exit_code": {"const": 0},
                            }
                        },
                        {
                            "properties": {
                                "conditions": {
                                    "contains": {
                                        "type": "object",
                                        "properties": {
                                            "id": {"const": "C02"},
                                            "result": {"const": "FALSE"},
                                        },
                                        "required": ["id", "result"],
                                    }
                                }
                            }
                        },
                    ]
                },
                "then": {
                    "properties": {
                        "verdict": {"enum": ["INCOMPLETE", "UNKNOWN"]},
                    }
                },
            },
        ],
        "x-spec-source": "_USER-PROMPTS.md:10631-10646",
        "x-sentinel": SENTINEL,
        "x-state": "SUCCESS",
        "x-unit-id": "ARC-0087",
        "x-min-artifact-bytes": MIN_ARTIFACT_BYTES,
        "x-applicability-matrix": matrix,
        "x-unit-classes": list(UNIT_CLASSES),
        "x-condition-catalog": [
            {
                "id": cid,
                "number": number,
                "name": name,
                "unknown_distinct_from_false": True,
            }
            for cid, number, name in CONDITION_SPEC
        ],
        "x-evaluation-rules": {
            "aggregate": (
                "COMPLETE only when every applicable condition is TRUE; "
                "INCOMPLETE when any applicable condition is FALSE; "
                "UNKNOWN when no applicable FALSE remains and at least one "
                "applicable UNKNOWN remains."
            ),
            "not_applicable_never_counts_as_pass": True,
            "unknown_never_collapses_to_false": True,
            "unknown_never_collapses_to_true": True,
            "exit_code_zero_alone_never_complete": True,
        },
        "x-anti-patterns": [
            "Exit code zero alone is never success.",
            "A plausible digest is not a receipt.",
            "A file path in text is not proof the file exists.",
        ],
        "x-consumer-call-site": (
            "command-center/p2-wave/probes/ARC-0087/probe2_vacuity_and_applicability.py "
            "Draft202012Validator(contract).validate(verdict)"
        ),
        "x-independent-reviewer": (
            "command-center/p2-wave/probes/ARC-0087/probe1_six_unit_breakdown.py "
            "structurally reviews 12 ids, UNKNOWN token, applicability matrix, "
            "and anti-pattern encoding before executing six live units."
        ),
    }


def main() -> int:
    CONTRACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    schema = build_schema()
    Draft_ok()
    CONTRACT_PATH.write_text(
        json.dumps(schema, indent=2, sort_keys=False) + "\n", encoding="utf-8"
    )
    print(f"wrote {CONTRACT_PATH.relative_to(CONTRACT_PATH.parents[3])} bytes={CONTRACT_PATH.stat().st_size}")
    print(SENTINEL)
    return 0


def Draft_ok() -> None:
    from jsonschema import Draft202012Validator

    Draft202012Validator.check_schema(build_schema())


if __name__ == "__main__":
    raise SystemExit(main())
