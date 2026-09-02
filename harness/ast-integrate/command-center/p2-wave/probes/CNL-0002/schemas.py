"""Reconstructed v1 charter schema and the two repair options."""
from __future__ import annotations

from constants import (
    CATALOGUE_SCHEMA_ID,
    CHARTER_OPTIONAL,
    CHARTER_SCHEMA_ID,
    OVERLAP_OPTIONAL,
    REQUIRED_12,
    UNION_SCHEMA_ID,
)


def _str_props(names: tuple[str, ...]) -> dict:
    return {n: {"type": "string", "minLength": 1} for n in names}


def v1_charter_schema() -> dict:
    """Draft 2020-12 object schema: 12 required, additionalProperties false.

    extra optional properties exist so a protocol record can share 4 key
    names without satisfying the required set.
    """
    properties = {
        **_str_props(REQUIRED_12),
        **_str_props(CHARTER_OPTIONAL),
        **_str_props(OVERLAP_OPTIONAL),
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": CHARTER_SCHEMA_ID,
        "title": "Reconstructed v1 Council Charter (CNL-0002 measurement fixture)",
        "type": "object",
        "required": list(REQUIRED_12),
        "properties": properties,
        "additionalProperties": False,
    }


def tagged_union_schema() -> dict:
    """ONE schema: discriminated union on synthetic artifact_type."""
    charter_branch = {
        "type": "object",
        "required": ["artifact_type", *REQUIRED_12],
        "properties": {
            "artifact_type": {"const": "council-charter-v1"},
            **_str_props(REQUIRED_12),
            **_str_props(CHARTER_OPTIONAL),
        },
        "additionalProperties": False,
    }
    catalogue_branch = {
        "type": "object",
        "required": ["artifact_type", "protocols", "presets"],
        "properties": {
            "artifact_type": {"const": "protocol-preset-catalogue"},
            "protocols": {"type": "array"},
            "presets": {"type": "array"},
            "schema_relationship": {"type": "string"},
            "spec_ref": {"type": "object"},
        },
        "additionalProperties": False,
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": UNION_SCHEMA_ID,
        "title": "Losing option: discriminated union on artifact_type",
        "oneOf": [charter_branch, catalogue_branch],
    }


def protocol_record_schema() -> dict:
    return {
        "type": "object",
        "required": ["id", "status"],
        "properties": {
            "id": {"type": "string", "minLength": 3},
            "status": {"type": "string", "minLength": 1},
            "title": {"type": "string"},
            "description": {},
            "name": {},
            "protocol_class": {},
            "roles": {"type": "array"},
            "anti_failure": {},
            "audit": {},
            "consensus": {},
            "discovery_only": {"type": "boolean"},
            "version": {},
            "seats": {},
            "budgets": {},
            "evidence": {},
            "outcomes": {},
            "integrity": {},
            "artifacts": {},
            "execution": {},
            "bound_preset_ids": {"type": "array"},
        },
        "additionalProperties": False,
    }


def preset_record_schema() -> dict:
    return {
        "type": "object",
        "required": ["id", "status", "bound_protocol"],
        "properties": {
            "id": {"type": "string", "minLength": 3},
            "status": {"type": "string", "minLength": 1},
            "bound_protocol": {"type": "string", "minLength": 3},
            "title": {"type": "string"},
            "roles": {"type": "array"},
            "voting": {},
            "stopping": {},
        },
        "additionalProperties": False,
    }


def catalogue_schema() -> dict:
    """TWO-schema repair: catalogue file with typed spec_ref edge."""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": CATALOGUE_SCHEMA_ID,
        "title": "Protocol/preset catalogue (not a Council Charter)",
        "type": "object",
        "required": ["protocols", "presets", "spec_ref"],
        "properties": {
            "schema_relationship": {"type": "string"},
            "spec_ref": {
                "type": "object",
                "required": ["schema_id", "edge", "target_kind"],
                "additionalProperties": False,
                "properties": {
                    "schema_id": {"type": "string", "minLength": 8},
                    "edge": {"const": "typed-reference"},
                    "target_kind": {"const": "council-charter-v1"},
                },
            },
            "protocols": {
                "type": "array",
                "minItems": 1,
                "items": {"$ref": "#/$defs/protocol_record"},
            },
            "presets": {
                "type": "array",
                "minItems": 1,
                "items": {"$ref": "#/$defs/preset_record"},
            },
        },
        "additionalProperties": False,
        "$defs": {
            "protocol_record": protocol_record_schema(),
            "preset_record": preset_record_schema(),
        },
    }


def spec_ref() -> dict:
    return {
        "schema_id": CHARTER_SCHEMA_ID,
        "edge": "typed-reference",
        "target_kind": "council-charter-v1",
    }
