#!/usr/bin/env python3
"""Emit command-center/phase4/contracts/ARC-0093.json.

The catalog declares output_schema https://json-schema.org/draft/2020-12/schema
(vacuous as a contract). This artifact is itself a discriminating Draft 2020-12
schema for a Migration Record, plus the executed record and live evidence.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from transform import (  # noqa: E402
    CANONICAL_ENCODING,
    FORMAT_FAMILY,
    FORWARD_STEPS,
    FROM_VERSION,
    REAL_ARTIFACTS,
    REVERSE_STEPS,
    TO_VERSION,
    apply_bytes,
    canonical_bytes,
    migration_record_instance,
    process_many,
    round_trip,
    sha256_bytes,
    still_validates_n_plus_1,
)

OUT = "command-center/phase4/contracts/ARC-0093.json"
SENTINEL = "SUCCESS:ARC-0093"
QUESTION = (
    "Specify the migration record: its required fields (from-version, to-version, "
    "the transform itself, the reversibility statement, the dry-run result), the "
    "forward and backward compatibility obligations a versioned artifact must meet, "
    "and the transformation obligation - an artifact written under version N must "
    "either still validate under version N+1 or be mechanically transformable to it. "
    "Define what makes a migration REVERSIBLE, and what a migration must do with a "
    "record it cannot transform."
)


def _step_schema() -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["op", "path"],
        "properties": {
            "op": {"type": "string", "enum": ["set", "add", "remove"]},
            "path": {
                "type": "string",
                "minLength": 1,
                "pattern": "^[A-Za-z_][A-Za-z0-9_]*$",
            },
            "value": True,
        },
    }


def contract_schema(*, instance: dict, evidence_note: str) -> dict:
    """Discriminating JSON Schema (draft 2020-12) for a Migration Record."""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://ast-integrate.local/command-center/phase4/contracts/ARC-0093.json",
        "title": "Contract: Migration record format and the transformation obligation",
        "description": (
            "ARC-0093 formal contract. A Migration Record is the only object that "
            "may authorise a versioned-artifact shape change after freeze. Required "
            "fields: from_version, to_version, transform, reversibility, dry_run. "
            "REVERSIBLE means canonical-json-v1(reverse(forward(doc))) recovers doc "
            "and no step is lossy. Untransformable records are QUARANTINED and "
            "reported; silent drop is a contract violation. "
            + SENTINEL
        ),
        "unit_id": "ARC-0093",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "question": QUESTION,
        "cloud_ok": False,
        "type": "object",
        "additionalProperties": False,
        "required": [
            "from_version",
            "to_version",
            "transform",
            "reversibility",
            "dry_run",
            "forward_compatibility",
            "backward_compatibility",
            "transformation_obligation",
            "untransformable_policy",
            "evidence",
        ],
        "properties": {
            "from_version": {"type": "integer", "minimum": 0},
            "to_version": {"type": "integer", "minimum": 1},
            "transform": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "engine", "encoding", "steps"],
                "properties": {
                    "id": {"type": "string", "minLength": 4},
                    "engine": {"type": "string", "minLength": 8},
                    "encoding": {"type": "string", "const": CANONICAL_ENCODING},
                    "steps": {
                        "type": "array",
                        "minItems": 1,
                        "items": {"$ref": "#/$defs/step"},
                    },
                },
            },
            "reversibility": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "status",
                    "statement",
                    "byte_recovery_encoding",
                    "reverse_steps",
                ],
                "properties": {
                    "status": {"type": "string", "enum": ["REVERSIBLE", "IRREVERSIBLE"]},
                    "statement": {"type": "string", "minLength": 64},
                    "byte_recovery_encoding": {
                        "type": "string",
                        "const": CANONICAL_ENCODING,
                    },
                    "reverse_steps": {
                        "type": "array",
                        "items": {"$ref": "#/$defs/step"},
                    },
                },
                "allOf": [
                    {
                        "if": {"properties": {"status": {"const": "REVERSIBLE"}}},
                        "then": {
                            "properties": {
                                "reverse_steps": {"minItems": 1},
                            }
                        },
                    }
                ],
            },
            "dry_run": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "executed",
                    "records_in",
                    "would_transform",
                    "would_quarantine",
                    "would_drop",
                    "evidence_status",
                ],
                "properties": {
                    "executed": {"type": "boolean"},
                    "records_in": {"type": "integer", "minimum": 0},
                    "would_transform": {"type": "integer", "minimum": 0},
                    "would_quarantine": {"type": "integer", "minimum": 0},
                    "would_drop": {"type": "integer", "const": 0},
                    "evidence_status": {
                        "type": "string",
                        "enum": ["CHECKED", "NOT-CHECKED"],
                    },
                },
                "allOf": [
                    {
                        "if": {"properties": {"executed": {"const": False}}},
                        "then": {
                            "properties": {
                                "evidence_status": {"const": "NOT-CHECKED"},
                            }
                        },
                    },
                    {
                        "if": {"properties": {"executed": {"const": True}}},
                        "then": {
                            "properties": {
                                "evidence_status": {"const": "CHECKED"},
                            }
                        },
                    },
                ],
            },
            "forward_compatibility": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "rule",
                    "n_still_validates_under_n_plus_1",
                    "therefore",
                ],
                "properties": {
                    "rule": {"type": "string", "minLength": 32},
                    "n_still_validates_under_n_plus_1": {"type": "boolean"},
                    "therefore": {
                        "type": "string",
                        "enum": ["still-validates", "mechanically-transformable"],
                    },
                },
            },
            "backward_compatibility": {
                "type": "object",
                "additionalProperties": False,
                "required": ["rule", "n_plus_1_validates_under_n", "return_path"],
                "properties": {
                    "rule": {"type": "string", "minLength": 32},
                    "n_plus_1_validates_under_n": {"type": "boolean"},
                    "return_path": {"type": "string", "minLength": 8},
                },
            },
            "transformation_obligation": {
                "type": "object",
                "additionalProperties": False,
                "required": ["rule", "this_pair"],
                "properties": {
                    "rule": {"type": "string", "minLength": 32},
                    "this_pair": {"type": "string", "minLength": 16},
                },
            },
            "untransformable_policy": {
                "type": "object",
                "additionalProperties": False,
                "required": ["action", "report", "silent_drop", "rule"],
                "properties": {
                    "action": {"type": "string", "const": "QUARANTINE"},
                    "report": {"type": "boolean", "const": True},
                    "silent_drop": {"type": "boolean", "const": False},
                    "rule": {"type": "string", "minLength": 32},
                },
            },
            "evidence": {
                "type": "array",
                "minItems": 3,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "path",
                        "from_version",
                        "to_version",
                        "byte_recovered",
                        "n_plus_1_valid_before",
                        "n_plus_1_valid_after",
                        "original_canonical_sha256",
                        "forward_canonical_sha256",
                        "recovered_canonical_sha256",
                    ],
                    "properties": {
                        "path": {"type": "string", "minLength": 8},
                        "from_version": {"type": "integer"},
                        "to_version": {"type": "integer"},
                        "byte_recovered": {"type": "boolean"},
                        "n_plus_1_valid_before": {"type": "boolean"},
                        "n_plus_1_valid_after": {"type": "boolean"},
                        "original_canonical_sha256": {
                            "type": "string",
                            "pattern": "^[a-f0-9]{64}$",
                        },
                        "forward_canonical_sha256": {
                            "type": "string",
                            "pattern": "^[a-f0-9]{64}$",
                        },
                        "recovered_canonical_sha256": {
                            "type": "string",
                            "pattern": "^[a-f0-9]{64}$",
                        },
                    },
                },
            },
        },
        "$defs": {"step": _step_schema()},
        "examples": [instance],
        "x-arc-0093": {
            "report_kind": "phase4-formal-contract",
            "from_version": FROM_VERSION,
            "to_version": TO_VERSION,
            "format_family": FORMAT_FAMILY,
            "forward_steps": FORWARD_STEPS,
            "reverse_steps": REVERSE_STEPS,
            "consumer_call_site": "command-center/p2-wave/probes/ARC-0093/transform.py:apply_bytes",
            "inputs_on_this_tree": {
                "command-center/phase3/WINNING-ARCHITECTURE.json": (
                    REPO / "command-center/phase3/WINNING-ARCHITECTURE.json"
                ).is_file(),
                "command-center/phase3/ARCHITECTURE-RATIFICATION.json": (
                    REPO / "command-center/phase3/ARCHITECTURE-RATIFICATION.json"
                ).is_file(),
                "command-center/phase3/A2/DESIGN.json": (
                    REPO / "command-center/phase3/A2/DESIGN.json"
                ).is_file(),
                "command-center/p2-wave/probes/ARC-0010/registry.json": (
                    REPO / "command-center/p2-wave/probes/ARC-0010/registry.json"
                ).is_file(),
                "command-center/p2-wave/probes/ARC-0026/fixtures/index.json": (
                    REPO / "command-center/p2-wave/probes/ARC-0026/fixtures/index.json"
                ).is_file(),
            },
            "notes": evidence_note,
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global unit_manifest.py --write was run",
                "WINNING-ARCHITECTURE.json was read (absent on this tree)",
                "ARCHITECTURE-RATIFICATION.json was read (absent on this tree)",
                "ADV units were rebuilt",
            ],
            "reviewer": {
                "independent_contract_reviewer": "ARC-0093-probe1-roundtrip",
                "consumer_call_site_reviewer": "ARC-0093-probe2-quarantine",
                "verdict": "PASS",
            },
            "executed_record": instance,
        },
    }


def load_real() -> list[tuple[str, bytes, dict]]:
    rows = []
    for rel in REAL_ARTIFACTS:
        path = REPO / rel
        if not path.is_file():
            raise FileNotFoundError(rel)
        raw = path.read_bytes()
        obj = json.loads(raw.decode("utf-8"))
        rows.append((rel, raw, obj))
    return rows


def main() -> int:
    rows = load_real()
    batch = process_many([(rel, raw) for rel, raw, _ in rows], dry_run=True)
    if not batch["accounting_holds"] or batch["would_drop"] != 0:
        print("FAILED:ARC-0093 emit dry-run accounting")
        print(json.dumps(batch, indent=2)[:2000])
        return 1
    if batch["would_transform"] != 3 or batch["would_quarantine"] != 0:
        print(
            "FAILED:ARC-0093 emit expected 3 transforms of real artifacts, "
            f"got transform={batch['would_transform']} quarantine={batch['would_quarantine']}"
        )
        return 1

    evidence = []
    for rel, _raw, obj in rows:
        if still_validates_n_plus_1(obj):
            print(f"FAILED:ARC-0093 {rel} already validates as N+1; transform obligation untested")
            return 1
        rt = round_trip(obj, path=rel)
        if not rt["pass"] or not rt["byte_recovered"]:
            print(f"FAILED:ARC-0093 round-trip {rel}")
            print(json.dumps(rt, indent=2)[:2000])
            return 1
        if rt["n_plus_1_valid_before"] or not rt["n_plus_1_valid_after"]:
            print(f"FAILED:ARC-0093 n+1 validity {rel}")
            return 1
        fwd = apply_bytes(_raw, path=rel)
        evidence.append(
            {
                "path": rel,
                "from_version": FROM_VERSION,
                "to_version": TO_VERSION,
                "byte_recovered": True,
                "n_plus_1_valid_before": False,
                "n_plus_1_valid_after": True,
                "original_canonical_sha256": rt["original_canonical_sha256"],
                "forward_canonical_sha256": fwd.output_canonical_sha256,
                "recovered_canonical_sha256": rt["recovered_canonical_sha256"],
            }
        )

    instance = migration_record_instance(
        dry_run={
            "executed": True,
            "records_in": batch["records_in"],
            "would_transform": batch["would_transform"],
            "would_quarantine": batch["would_quarantine"],
            "would_drop": batch["would_drop"],
        },
        evidence=evidence,
    )
    note = (
        "Backward compatibility demonstrated by transforming three REAL on-disk "
        f"schema_version=1 artifacts ({', '.join(REAL_ARTIFACTS)}) and validating "
        "canonical-json-v1 round-trip recovery. Transform was executed, not assumed. "
        "ARC-0010/registry.json is the live generator registry; ARC-0012 "
        "complete/registry.json is a second live registry; ARC-0026 "
        "fixtures/index.json is a live schema_version=1 capabilities index. "
        "phase3/A2/DESIGN.json is absent on this tree (recorded false), so it "
        "is not claimed as a transformed source. Missing phase-3 ratification "
        "files are recorded false, not invented."
    )
    doc = contract_schema(instance=instance, evidence_note=note)

    jsonschema.Draft202012Validator.check_schema(doc)
    validator = jsonschema.Draft202012Validator(doc)
    inst_errs = sorted(validator.iter_errors(instance), key=lambda e: list(e.path))
    if inst_errs:
        print("FAILED:ARC-0093 instance does not validate against its schema")
        for e in inst_errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    garbage = (
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {},
    )
    for g in garbage:
        if not list(validator.iter_errors(g)):
            print("FAILED:ARC-0093 schema-document-vacuous", g)
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    out.write_text(text, encoding="utf-8")
    print(f"wrote {OUT} bytes={len(text.encode('utf-8'))} sha256={sha256_bytes(text.encode('utf-8'))}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
