"""Field-space examples and coverage for schema types (TST-0116)."""
from __future__ import annotations

from typing import Any

from proptest.fields import GENERATED_TYPES, REQUIRED_BY_TYPE


def field_space_examples(kind: str) -> list[dict[str, Any]]:
    if kind == "work_unit":
        return [
            {"id": "IMP-0001", "output_path": "command-center/receipts/IMP-0001.json"},
            {"id": "TST-0001", "output_path": "x.json", "title": "t"},
        ]
    if kind == "receipt":
        return [
            {"unit_id": "IMP-0001", "state": "SUCCESS"},
            {"unit_id": "TST-0001", "state": "SUCCESS", "sentinel": "SUCCESS:TST-0001"},
        ]
    if kind == "council_spec":
        return [
            {"id": "spec.a", "seats": [{"id": "s1"}]},
            {"id": "spec.b", "seats": [{"id": "s1"}, {"id": "s2"}], "scheduler": {}},
        ]
    if kind == "workflow_dag":
        return [
            {"id": "wf-a", "nodes": [{"id": "n1"}], "edges": []},
            {"id": "wf-b", "nodes": [{"id": "n1"}, {"id": "n2"}], "edges": [["n1", "n2"]]},
        ]
    return []


def coverage_for(kind: str) -> dict[str, Any]:
    required = list(REQUIRED_BY_TYPE.get(kind) or ())
    examples = field_space_examples(kind)
    missing = [f for f in required if any(f not in ex for ex in examples)]
    return {
        "pass": kind in GENERATED_TYPES and not missing and bool(examples),
        "missing_fields": missing,
        "n_examples": len(examples),
        "type": kind,
    }
