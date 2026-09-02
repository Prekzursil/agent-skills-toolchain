#!/usr/bin/env python3
"""CouncilSpec v2 root envelope: discriminated union over charter / protocol / preset.

Minimal envelope such that reconstructed 58+72 catalogue records validate unchanged
and a v1 charter migrates with zero information loss by wrapping the one property
whose v1 shape cannot accept catalogue records: `stopping` (string expression ->
`{mode: expression, expression}` object).
"""
from __future__ import annotations

from fixtures import (
    PRESET_KEYS,
    PROTOCOL_KEYS,
    SHAPE_CHANGE_PROPERTY,
    V1_PROPERTIES,
    V1_REQUIRED,
)

SENTINEL = "SUCCESS:CNL-0001"
ARTIFACT_REL = (
    "command-center/design/council/"
    "CNL-0001-councilspec-v2-root-envelope-that-supersedes-council-chart.schema.json"
)
META_REL = "command-center/schema/councilspec.v2.schema.json"
QUESTION = (
    "What is the minimal CouncilSpec v2 root envelope such that every one of the "
    "58 protocol records and 72 preset records in 12-COUNCIL-PROTOCOLS-AND-PRESETS.json "
    "validates against it, AND a v1 Council Charter document (13 properties, 12 required) "
    "migrates forward with zero information loss - and which v1 property must change "
    "shape for that to be true?"
)


def _str_arr() -> dict:
    return {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}}


def _voting() -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["rule", "quorum"],
        "properties": {
            "rule": {"type": "string", "minLength": 1},
            "quorum": {"type": "integer", "minimum": 1},
        },
    }


def _evidence() -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["standard"],
        "properties": {
            "standard": {"type": "string", "minLength": 1},
            "hash_inputs": {"type": "boolean"},
        },
    }


def _anti_failure() -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["on_split", "no_silent_average"],
        "properties": {
            "on_split": {"type": "string", "minLength": 1},
            "no_silent_average": {"type": "boolean"},
        },
    }


def _audit() -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["persist_transcript", "hash_inputs"],
        "properties": {
            "persist_transcript": {"type": "boolean"},
            "hash_inputs": {"type": "boolean"},
            "replay": {"type": "boolean"},
            "calibration": {"type": "boolean"},
            "determinism": {"type": "boolean"},
            "persistence": {"type": "boolean"},
            "privacy": {"type": "string"},
            "resume": {"type": "boolean"},
        },
    }


def _consensus() -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["reducer"],
        "properties": {
            "reducer": {"type": "string", "minLength": 1},
            "local_completion_forbidden": {"type": "boolean"},
        },
    }


def _stopping_caps() -> dict:
    """Catalogue stopping object — accepted unchanged on protocol/preset records."""
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["max_rounds", "on_timeout"],
        "properties": {
            "max_rounds": {"type": "integer", "minimum": 1},
            "on_timeout": {"type": "string", "minLength": 1},
            "on_unresolved": {"type": "string", "minLength": 1},
        },
    }


def _stopping_expression() -> dict:
    """Migrated v1 stopping_expr: the ONE v1 property whose shape changes."""
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["mode", "expression"],
        "properties": {
            "mode": {"const": "expression"},
            "expression": {"type": "string", "minLength": 1},
        },
    }


def _charter_v2() -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(V1_REQUIRED),
        "properties": {
            "charter": {
                "type": "object",
                "additionalProperties": False,
                "required": ["objective"],
                "properties": {
                    "objective": {"type": "string", "minLength": 1},
                    "risk_tier": {"type": "string"},
                    "desired_output": {"type": "string"},
                    "success_criteria": {"type": "string"},
                    "consensus_intent": {"type": "string"},
                },
            },
            "participants": {
                "type": "array",
                "minItems": 1,
                "items": {"$ref": "#/$defs/seat"},
            },
            "roles": _str_arr(),
            "engagement": {
                "type": "object",
                "additionalProperties": False,
                "required": ["min_turns"],
                "properties": {
                    "min_turns": {"type": "integer", "minimum": 1},
                    "max_inactivity": {"type": "integer", "minimum": 0},
                },
            },
            "budgets": {
                "type": "object",
                "additionalProperties": False,
                "required": ["tokens"],
                "properties": {
                    "tokens": {"type": "integer", "minimum": 1},
                    "time_seconds": {"type": "integer", "minimum": 1},
                },
            },
            "evidence": _evidence(),
            "voting": _voting(),
            "stopping": {"$ref": "#/$defs/stopping_expression"},
            "outcomes": {
                "type": "object",
                "additionalProperties": False,
                "required": ["allowed"],
                "properties": {
                    "allowed": {
                        "type": "array",
                        "minItems": 1,
                        "items": {"$ref": "#/$defs/outcome"},
                    }
                },
            },
            "integrity": {
                "type": "object",
                "additionalProperties": False,
                "required": ["hash_transcript"],
                "properties": {"hash_transcript": {"type": "boolean"}},
            },
            "artifacts": {
                "type": "object",
                "additionalProperties": False,
                "required": ["persist"],
                "properties": {"persist": {"type": "boolean"}},
            },
            "execution": {
                "type": "object",
                "additionalProperties": False,
                "required": ["runtime"],
                "properties": {"runtime": {"type": "string", "minLength": 1}},
            },
            "meta": {
                "type": "object",
                "additionalProperties": False,
                "properties": {"schema_version": {"type": "string"}},
            },
        },
    }


def _protocol_record() -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(PROTOCOL_KEYS),
        "properties": {
            "id": {"type": "string", "pattern": "^P[0-9]{2}$"},
            "family": {"type": "string", "minLength": 3},
            "name": {"type": "string", "minLength": 3},
            "description": {"type": "string", "minLength": 3},
            "status": {"type": "string", "minLength": 3},
            "anti_failure": _anti_failure(),
            "audit": _audit(),
            "voting": _voting(),
            "consensus": _consensus(),
            "stopping": {"$ref": "#/$defs/stopping_caps"},
            "roles": _str_arr(),
            "evidence": _evidence(),
            "turn_model": {"type": "string", "minLength": 3},
        },
    }


def _preset_record() -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(PRESET_KEYS),
        "properties": {
            "id": {"type": "string", "minLength": 3},
            "name": {"type": "string", "minLength": 3},
            "status": {"type": "string", "minLength": 3},
            "description": {"type": "string", "minLength": 3},
            "family": {"type": "string", "minLength": 3},
            "base_spec": {"type": "string", "minLength": 3},
            "default_binding": {"type": "string", "minLength": 3},
            "editable_dials": {"type": "array", "minItems": 1, "items": {"type": "string"}},
            "editable": {"type": "boolean"},
            "roles": _str_arr(),
            "anti_failure": _anti_failure(),
            "audit": _audit(),
            "voting": _voting(),
            "consensus": _consensus(),
            "stopping": {"$ref": "#/$defs/stopping_caps"},
            "evidence": _evidence(),
            "outcome": {"$ref": "#/$defs/outcome"},
            "protocol_binding": {"type": "string", "minLength": 3},
            "anonymity": {"type": "string", "minLength": 3},
            "replay": {"type": "boolean"},
        },
    }


def delivery_block() -> dict:
    return {
        "unit_id": "CNL-0001",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "question": QUESTION,
        "answer": (
            "The minimal v2 root envelope is a Draft 2020-12 oneOf over three strict "
            "record types (charter_v2, protocol_record, preset_record) sharing $defs "
            "for the overlapping axes. Catalogue records validate unchanged because "
            "protocol/preset branches accept their existing keys and the caps-shaped "
            "stopping object. A v1 charter migrates by wrapping stopping: the v1 "
            "string $defs.stopping_expr becomes {mode:expression, expression:<string>}. "
            "No v1 property is dropped; that wrap is the only shape change. "
            "A discriminated union without that wrap cannot accept both a v1 charter "
            "and the catalogue stopping object under one named property."
        ),
        "v1_property_that_changes_shape": SHAPE_CHANGE_PROPERTY,
        "v1_properties": list(V1_PROPERTIES),
        "v1_required": list(V1_REQUIRED),
        "sources_on_this_tree": {
            "11-COUNCIL-SPECIFICATION.schema.json": False,
            "12-COUNCIL-PROTOCOLS-AND-PRESETS.json": False,
        },
        "reconstruction": (
            "Harness-restore inputs are absent. Fixtures reconstruct 13/12 charter "
            "sections (IMP-0261), 58 P-ids (CNL-0038..0046), 72 presets / 20 keys "
            "(CNL-0101), and C-M01 (CNL-0002). Not a byte copy of unread files."
        ),
        "ppj_record_ids": {
            "protocols": [f"P{i:02d}" for i in range(1, 59)],
            "presets_head": ["C-M01"] + [f"C-{i:02d}" for i in range(2, 8)],
            "presets_count": 72,
            "note": "PPJ = protocol/preset JSON record ids from the reconstructed catalogue",
        },
    }


def v2_envelope() -> dict:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://ast-integrate.local/schema/councilspec-v2-root-envelope.schema.json",
        "title": "CouncilSpec v2 root envelope that supersedes Council Charter v1",
        "description": (
            f"{SENTINEL}. Minimal oneOf envelope: charter_v2 | protocol_record | "
            f"preset_record. Shape-changing v1 property: {SHAPE_CHANGE_PROPERTY}."
        ),
        "state": "SUCCESS",
        "x-cnl-0001-delivery": delivery_block(),
        "oneOf": [
            {"$ref": "#/$defs/charter_v2"},
            {"$ref": "#/$defs/protocol_record"},
            {"$ref": "#/$defs/preset_record"},
        ],
        "$defs": {
            "charter_v2": _charter_v2(),
            "protocol_record": _protocol_record(),
            "preset_record": _preset_record(),
            "stopping_expression": _stopping_expression(),
            "stopping_caps": _stopping_caps(),
            "seat": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "role"],
                "properties": {
                    "id": {"type": "string", "minLength": 1},
                    "model": {"type": "string"},
                    "vendor": {"type": "string"},
                    "expertise": {"type": "string"},
                    "role": {"type": "string", "minLength": 1},
                    "authority": {"type": "string"},
                    "vote_weight": {"type": "number"},
                    "tools": {"type": "array", "items": {"type": "string"}},
                    "effort": {"type": "string"},
                    "context": {"type": "string"},
                },
            },
            "outcome": {
                "type": "string",
                "enum": [
                    "decision",
                    "conditional-decision",
                    "no-decision",
                    "irreducible-disagreement",
                    "dissent-with-minority-report",
                    "proof-of-impossibility",
                    "accept",
                    "reject",
                    "defer",
                    "escalate",
                    "hung",
                    "timeout",
                    "owner-override",
                    "replay",
                    "split",
                    "merge",
                    "unknown",
                ],
            },
        },
    }


def meta_schema() -> dict:
    """Contract for the CNL-0001 envelope document (catalog output_schema)."""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://ast-integrate.local/schema/councilspec.v2.schema.json",
        "title": "CouncilSpec v2 envelope design document",
        "type": "object",
        "additionalProperties": True,
        "required": [
            "$schema",
            "$id",
            "title",
            "description",
            "oneOf",
            "$defs",
            "x-cnl-0001-delivery",
            "state",
        ],
        "properties": {
            "$schema": {"type": "string", "minLength": 8},
            "$id": {"type": "string", "minLength": 8},
            "title": {"type": "string", "minLength": 8},
            "description": {"type": "string", "minLength": 16},
            "state": {"type": "string", "enum": ["SUCCESS"]},
            "oneOf": {"type": "array", "minItems": 3},
            "$defs": {
                "type": "object",
                "required": [
                    "charter_v2",
                    "protocol_record",
                    "preset_record",
                    "stopping_expression",
                    "stopping_caps",
                ],
            },
            "x-cnl-0001-delivery": {
                "type": "object",
                "additionalProperties": True,
                "required": [
                    "unit_id",
                    "sentinel",
                    "answer",
                    "v1_property_that_changes_shape",
                    "v1_properties",
                    "v1_required",
                    "sources_on_this_tree",
                ],
                "properties": {
                    "unit_id": {"const": "CNL-0001"},
                    "sentinel": {"const": SENTINEL},
                    "state": {"type": "string", "enum": ["SUCCESS"]},
                    "answer": {"type": "string", "minLength": 80},
                    "v1_property_that_changes_shape": {"const": "stopping"},
                    "v1_properties": {
                        "type": "array",
                        "minItems": 13,
                        "maxItems": 13,
                        "items": {"type": "string"},
                    },
                    "v1_required": {
                        "type": "array",
                        "minItems": 12,
                        "maxItems": 12,
                        "items": {"type": "string"},
                    },
                    "sources_on_this_tree": {"type": "object"},
                },
            },
        },
    }
