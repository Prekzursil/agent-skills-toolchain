"""JSON Schema 2020-12 for the artifact envelope and ARTIFACT-MANIFEST.json."""
from __future__ import annotations

from typing import Any

MANDATED = (
    "artifact_id",
    "producing_unit",
    "content_hash",
    "byte_size",
    "schema_reference",
    "sentinel",
    "evidence_anchors",
    "retention_class",
    "manifest_registration",
)

UNIT_RE = "^[A-Z]{2,5}-[0-9]{4}$"
ART_ID_RE = "^[A-Z]{2,5}-[0-9]{4}:[A-Za-z0-9._-]{1,64}$"
HEX64_RE = "^[0-9a-f]{64}$"
PATH_RE = "^[A-Za-z0-9._/=+-][A-Za-z0-9._/=+-]*$"


def _if_class_floor(cls: str, floor: int) -> dict[str, Any]:
    return {
        "if": {
            "properties": {"artifact_class": {"const": cls}},
            "required": ["artifact_class"],
        },
        "then": {
            "properties": {
                "byte_size": {"type": "integer", "minimum": floor}
            }
        },
    }


def build(floors: dict[str, int], derivation: dict[str, Any]) -> dict[str, Any]:
    classes = sorted(floors)
    class_allof = [_if_class_floor(cls, int(floors[cls])) for cls in classes]
    envelope: dict[str, Any] = {
        "type": "object",
        "additionalProperties": False,
        "required": list(MANDATED) + ["path", "artifact_class"],
        "properties": {
            "artifact_id": {"type": "string", "pattern": ART_ID_RE},
            "producing_unit": {"type": "string", "pattern": UNIT_RE},
            "path": {"type": "string", "minLength": 3, "pattern": PATH_RE},
            "artifact_class": {"type": "string", "enum": classes},
            "content_hash": {"$ref": "#/$defs/content_hash"},
            "byte_size": {"type": "integer", "minimum": 2},
            "schema_reference": {"type": "string", "minLength": 8},
            "sentinel": {"type": "string", "minLength": 8},
            "evidence_anchors": {
                "type": "array",
                "minItems": 1,
                "items": {"$ref": "#/$defs/evidence_anchor"},
            },
            "retention_class": {
                "type": "string",
                "enum": ["session", "unit", "program", "archival"],
            },
            "manifest_registration": {
                "$ref": "#/$defs/manifest_registration_record"
            },
        },
        "allOf": class_allof,
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "command-center/phase4/contracts/ARC-0084.json",
        "title": (
            "Contract: Artifact envelope schema, integrity digest and "
            "manifest registration"
        ),
        "description": (
            "Canonical envelope for a produced artifact: artifact id, producing "
            "unit, content hash, byte size, schema reference, sentinel, evidence "
            "anchors, retention class, and the manifest registration record. "
            "An artifact that exists on disk but is absent from the on-disk "
            "ARTIFACT-MANIFEST.json is not complete. Size floors are derived "
            "from the live distribution (never one byte). SUCCESS:ARC-0084"
        ),
        "$defs": {
            "content_hash": {
                "type": "object",
                "additionalProperties": False,
                "required": ["alg", "hex"],
                "properties": {
                    "alg": {"const": "sha256"},
                    "hex": {"type": "string", "pattern": HEX64_RE},
                },
            },
            "evidence_anchor": {
                "type": "object",
                "additionalProperties": False,
                "required": ["path", "claim"],
                "properties": {
                    "path": {"type": "string", "minLength": 3},
                    "line": {"type": "integer", "minimum": 1},
                    "snippet": {"type": "string", "minLength": 4},
                    "claim": {"type": "string", "minLength": 8},
                },
            },
            "manifest_registration_record": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "manifest_path",
                    "path",
                    "sha256",
                    "bytes",
                    "present",
                    "producing_unit",
                ],
                "properties": {
                    "manifest_path": {
                        "type": "string",
                        "pattern": r".*ARTIFACT-MANIFEST\.json$",
                    },
                    "path": {"type": "string", "minLength": 3},
                    "sha256": {
                        "type": "string",
                        "pattern": r"^([0-9a-f]{64}|\(self\)|)$",
                    },
                    "bytes": {"type": "integer", "minimum": 0},
                    "present": {"type": "boolean"},
                    "producing_unit": {"type": "string", "pattern": UNIT_RE},
                    "artifact_id": {"type": "string"},
                    "role": {"type": "string"},
                },
            },
            "artifact_envelope": envelope,
            "artifact_manifest": {
                "type": "object",
                "additionalProperties": True,
                "required": [
                    "schema_version",
                    "verified_on_disk",
                    "artifacts",
                ],
                "properties": {
                    "schema_version": {"type": "integer", "minimum": 1},
                    "contract": {"type": "string", "minLength": 8},
                    "derivation": {"type": "string"},
                    "verified_on_disk": {"const": True},
                    "present": {"type": "integer", "minimum": 0},
                    "expected": {"type": "integer", "minimum": 0},
                    "artifacts": {
                        "type": "array",
                        "items": {
                            "$ref": "#/$defs/manifest_registration_record"
                        },
                    },
                },
            },
        },
        "$ref": "#/$defs/artifact_envelope",
        "unit_id": "ARC-0084",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ARC-0084",
        "min_bytes_threshold": max(floors.values()),
        "completeness_rule": (
            "An artifact is complete only if (1) the path exists on disk, "
            "(2) CRLF-normalized byte size meets the class floor, (3) the "
            "sha256 of those bytes matches the envelope content_hash, and "
            "(4) ARTIFACT-MANIFEST.json, read from disk, contains a present=true "
            "row for that path whose sha256 matches the live digest. A path "
            "that exists but is unregistered fails. A plausible digest for an "
            "absent file fails."
        ),
        "size_floors": floors,
        "size_floor_derivation": derivation,
        "mandated_envelope_fields": list(MANDATED),
        "tests_required": [
            "Registration assertion: an artifact on disk but unregistered must fail the predicate",
            "Digest control: mutate one byte of an artifact and assert the digest check fires",
        ],
        "x-reviewers": {
            "independent_contract_reviewer": (
                "command-center/p2-wave/probes/ARC-0084/reviewer.py"
            ),
            "consumer_call_site": (
                "command-center/p2-wave/probes/ARC-0084/consumer.py"
            ),
        },
        "x-predicate": "command-center/p2-wave/probes/ARC-0084/predicate.py",
    }
