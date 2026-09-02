"""Local discriminator for REL-0019.

The catalog shim command-center/schema/telemetry-threshold-receipt.schema.json
is a $ref to https://ast-integrate.invalid/... . Distro jsonschema 4.10 tries
the network and raises RefResolutionError; platform/lib/schema_resolver.py
needs jsonschema>=4.18 `registry=` which this worktree does not have.

G-1 does not require live $ref resolution. This Draft-7 gate still rejects
garbage and requires the telemetry-threshold payload (kind, observations,
control_ids, five gate rows).
"""
from __future__ import annotations

LOCAL_GATE = {
    "type": "object",
    "required": [
        "schema_version",
        "unit_id",
        "state",
        "sentinel",
        "spec_anchor",
        "min_bytes_threshold",
        "artifacts",
        "evidence",
        "timestamps",
        "retry",
        "report",
        "tests",
        "negative_controls",
        "reviewer",
        "manifest_registration",
        "downstream_consumers",
        "residual_unknowns",
    ],
    "properties": {
        "schema_version": {"const": 1},
        "unit_id": {"const": "REL-0019"},
        "state": {"const": "SUCCESS"},
        "sentinel": {"type": "string", "pattern": "^SUCCESS:REL-0019$"},
        "spec_anchor": {"type": "string", "minLength": 8},
        "min_bytes_threshold": {"type": "integer", "minimum": 1024},
        "artifacts": {"type": "array", "minItems": 1},
        "evidence": {"type": "array", "minItems": 2},
        "tests": {"type": "array", "minItems": 4},
        "negative_controls": {"type": "array", "minItems": 1},
        "reviewer": {
            "type": "object",
            "required": ["reviewer_id", "verdict", "independent"],
            "properties": {
                "verdict": {"const": "PASS"},
                "independent": {"const": True},
            },
        },
        "manifest_registration": {
            "type": "object",
            "required": ["registered", "manifest_path"],
            "properties": {"registered": {"const": True}},
        },
        "downstream_consumers": {"type": "array", "minItems": 1},
        "residual_unknowns": {"type": "array", "minItems": 1},
        "timestamps": {
            "type": "object",
            "required": ["started_at", "ended_at"],
        },
        "retry": {
            "type": "object",
            "required": ["count", "policy"],
        },
        "report": {
            "type": "object",
            "required": ["kind", "observations", "control_ids", "gates"],
            "properties": {
                "kind": {"const": "telemetry-threshold-receipt"},
                "observations": {
                    "type": "array",
                    "minItems": 5,
                    "items": {
                        "type": "object",
                        "required": ["name", "measured", "method", "anchor"],
                    },
                },
                "control_ids": {"type": "array", "minItems": 1},
                "gates": {"type": "array", "minItems": 5},
            },
        },
    },
}
