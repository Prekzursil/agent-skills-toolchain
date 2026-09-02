#!/usr/bin/env python3
"""Marketplace registry-entry JSON Schema (Draft 2020-12) for ARC-0079.

Author-side module. Probe 2 must validate using the schema embedded in the
live contract, not by importing this file as the consumer call site.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from jsonschema import Draft202012Validator

SEMVER = r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
NS = r"^[a-z][a-z0-9-]{1,62}$"
NAME = r"^[a-z][a-z0-9-]{0,63}$"
PKG = r"^[a-z][a-z0-9-]{1,62}/[a-z][a-z0-9-]{0,63}$"
SHA256 = r"^[a-f0-9]{64}$"
UTC = r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$"
URI = r"^[a-z][a-z0-9+.-]*:.+"
CHANNEL = r"^(stable|beta|nightly|[a-z][a-z0-9-]{0,31})$"
PERM = r"^[a-z][a-z0-9_.-]{1,63}$"


def _str(pattern: str, min_len: int = 1) -> dict:
    return {"type": "string", "minLength": min_len, "pattern": pattern}


PROVENANCE = {
    "type": "object",
    "additionalProperties": False,
    "required": ["artifact_sha256", "source_uri", "builder_id", "built_at"],
    "properties": {
        "artifact_sha256": _str(SHA256, 64),
        "source_uri": _str(URI, 8),
        "builder_id": {"type": "string", "minLength": 3, "maxLength": 128},
        "built_at": _str(UTC, 20),
        "git_commit": {"type": "string", "pattern": r"^[a-f0-9]{40}$"},
        "tree_hash": _str(SHA256, 64),
    },
}

SIGNATURE = {
    "type": "object",
    "additionalProperties": False,
    "required": ["algorithm", "key_id", "signature_uri", "digest_sha256"],
    "properties": {
        "algorithm": {"type": "string", "enum": ["ed25519", "sigstore-bundle"]},
        "key_id": {"type": "string", "minLength": 8, "maxLength": 128},
        "signature_uri": _str(URI, 8),
        "digest_sha256": _str(SHA256, 64),
    },
}

SBOM = {
    "type": "object",
    "additionalProperties": False,
    "required": ["media_type", "uri", "digest_sha256"],
    "properties": {
        "media_type": {
            "type": "string",
            "enum": [
                "application/spdx+json",
                "application/vnd.cyclonedx+json",
            ],
        },
        "uri": _str(URI, 8),
        "digest_sha256": _str(SHA256, 64),
    },
}

LICENSE = {
    "type": "object",
    "additionalProperties": False,
    "required": ["spdx_id"],
    "properties": {
        "spdx_id": {"type": "string", "minLength": 3, "maxLength": 64},
        "uri": _str(URI, 8),
    },
}

VULN = {
    "type": "object",
    "additionalProperties": False,
    "required": ["status", "advisory_ids"],
    "properties": {
        "status": {
            "type": "string",
            "enum": ["none_known", "advisory_open", "patched"],
        },
        "advisory_ids": {
            "type": "array",
            "items": {"type": "string", "minLength": 3},
        },
    },
}

QUALITY = {
    "type": "object",
    "additionalProperties": False,
    "required": ["score", "method"],
    "properties": {
        "score": {"type": "number", "minimum": 0, "maximum": 100},
        "method": {"type": "string", "minLength": 3, "maxLength": 64},
        "evidence_uri": _str(URI, 8),
    },
}

DEPENDENCY = {
    "type": "object",
    "additionalProperties": False,
    "required": ["package_id", "constraint"],
    "properties": {
        "package_id": _str(PKG, 5),
        "constraint": {"type": "string", "minLength": 1, "maxLength": 64},
        "optional": {"type": "boolean"},
    },
}

COMPAT = {
    "type": "object",
    "additionalProperties": False,
    "required": ["platforms", "client"],
    "properties": {
        "platforms": {
            "type": "array",
            "minItems": 1,
            "items": {"type": "string", "enum": ["linux", "darwin", "win32"]},
            "uniqueItems": True,
        },
        "client": {
            "type": "object",
            "additionalProperties": False,
            "required": ["id", "min_version"],
            "properties": {
                "id": {"type": "string", "minLength": 3, "maxLength": 64},
                "min_version": _str(SEMVER, 5),
                "max_version": _str(SEMVER, 5),
            },
        },
    },
}

PERMISSION = {
    "type": "object",
    "additionalProperties": False,
    "required": ["id", "required"],
    "properties": {
        "id": _str(PERM, 3),
        "required": {"type": "boolean"},
        "scope": {"type": "string", "enum": ["workspace", "user", "system"]},
    },
}

DEPRECATION = {
    "type": "object",
    "additionalProperties": False,
    "required": ["message", "deprecated_at"],
    "properties": {
        "message": {"type": "string", "minLength": 8, "maxLength": 512},
        "deprecated_at": _str(UTC, 20),
        "successor": _str(PKG, 5),
    },
}

REVOCATION = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "reason",
        "effective_at",
        "signed_list_ref",
        "issuer",
        "client_action",
    ],
    "properties": {
        "reason": {
            "type": "string",
            "enum": [
                "compromised-signing-key",
                "malicious-content",
                "legal-takedown",
                "owner-withdrawn",
            ],
        },
        "effective_at": _str(UTC, 20),
        "signed_list_ref": {"type": "string", "minLength": 8, "maxLength": 256},
        "issuer": {"type": "string", "enum": ["owner", "registry"]},
        "client_action": {
            "type": "string",
            "const": "refuse-install-and-surface-on-refresh",
        },
    },
}

TOMBSTONE = {
    "type": "object",
    "additionalProperties": False,
    "required": ["deleted_at", "reason"],
    "properties": {
        "deleted_at": _str(UTC, 20),
        "reason": {"type": "string", "minLength": 8, "maxLength": 256},
    },
}

VERSION = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "version",
        "channels",
        "lifecycle",
        "presence",
        "dependencies",
        "compatibility",
        "permissions",
        "provenance",
        "signature",
        "sbom",
        "license",
        "vulnerability",
        "quality",
    ],
    "properties": {
        "version": _str(SEMVER, 5),
        "channels": {
            "type": "array",
            "minItems": 1,
            "items": _str(CHANNEL, 4),
            "uniqueItems": True,
        },
        "lifecycle": {
            "type": "string",
            "enum": ["published", "deprecated", "revoked", "deleted"],
        },
        "presence": {"type": "string", "enum": ["retained", "tombstone"]},
        "dependencies": {"type": "array", "items": DEPENDENCY},
        "compatibility": COMPAT,
        "permissions": {"type": "array", "items": PERMISSION},
        "provenance": PROVENANCE,
        "signature": SIGNATURE,
        "sbom": SBOM,
        "license": LICENSE,
        "vulnerability": VULN,
        "quality": QUALITY,
        "deprecation": DEPRECATION,
        "revocation": REVOCATION,
        "tombstone": TOMBSTONE,
    },
    "allOf": [
        {
            "if": {
                "properties": {"lifecycle": {"const": "published"}},
                "required": ["lifecycle"],
            },
            "then": {
                "properties": {"presence": {"const": "retained"}},
                "not": {
                    "anyOf": [
                        {"required": ["deprecation"]},
                        {"required": ["revocation"]},
                        {"required": ["tombstone"]},
                    ]
                },
            },
        },
        {
            "if": {
                "properties": {"lifecycle": {"const": "deprecated"}},
                "required": ["lifecycle"],
            },
            "then": {
                "required": ["deprecation"],
                "properties": {"presence": {"const": "retained"}},
                "not": {
                    "anyOf": [
                        {"required": ["revocation"]},
                        {"required": ["tombstone"]},
                    ]
                },
            },
        },
        {
            "if": {
                "properties": {"lifecycle": {"const": "revoked"}},
                "required": ["lifecycle"],
            },
            "then": {
                "required": ["revocation"],
                "properties": {"presence": {"const": "retained"}},
                "not": {"required": ["tombstone"]},
            },
        },
        {
            "if": {
                "properties": {"lifecycle": {"const": "deleted"}},
                "required": ["lifecycle"],
            },
            "then": {
                "required": ["tombstone"],
                "properties": {"presence": {"const": "tombstone"}},
                "not": {"required": ["revocation"]},
            },
        },
    ],
}

SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "command-center/phase4/contracts/ARC-0079.registry-entry.schema.json",
    "title": "Marketplace registry index entry (ARC-0079)",
    "description": (
        "One package record in the canonical registry index: identity, "
        "version list with channels, dependencies, compatibility, "
        "permissions, provenance, signature, SBOM, license, vulnerability "
        "status, quality score, and lifecycle. A revoked version stays in "
        "the index (presence=retained) so an already-installed client that "
        "refreshes can observe it. A deleted version is a tombstone without "
        "a revocation object. Absence of a row is not a revocation signal. "
        "SUCCESS:ARC-0079"
    ),
    "type": "object",
    "additionalProperties": False,
    "required": ["package_id", "namespace", "name", "versions"],
    "properties": {
        "package_id": _str(PKG, 5),
        "namespace": _str(NS, 2),
        "name": _str(NAME, 1),
        "versions": {
            "type": "array",
            "minItems": 1,
            "items": VERSION,
        },
    },
    "x-package-id-rule": "package_id MUST equal namespace + '/' + name (consumer-enforced)",
    "x-revocation-vs-deletion": {
        "revoked": "lifecycle=revoked AND presence=retained AND revocation object; row remains",
        "deleted": "lifecycle=deleted AND presence=tombstone AND tombstone object AND no revocation",
        "client_refresh": (
            "Installed clients learn revocation by matching package_id+version "
            "on a retained revoked row after index refresh, never by treating "
            "a missing row as revoked."
        ),
    },
}


def canonical_dumps(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def schema_digest(schema: dict | None = None) -> str:
    body = canonical_dumps(schema if schema is not None else SCHEMA)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def package_id_errors(instance: dict) -> list[str]:
    ns = instance.get("namespace")
    name = instance.get("name")
    pid = instance.get("package_id")
    if not isinstance(ns, str) or not isinstance(name, str) or not isinstance(pid, str):
        return ["package_id-fields-missing"]
    if pid != f"{ns}/{name}":
        return [f"package_id-mismatch want={ns}/{name} got={pid}"]
    return []


def iter_errors(instance: Any, schema: dict | None = None) -> list[str]:
    sch = schema if schema is not None else SCHEMA
    Draft202012Validator.check_schema(sch)
    errs = [
        f"{'/'.join(str(p) for p in e.absolute_path) or '$'}: {e.message}"
        for e in Draft202012Validator(sch).iter_errors(instance)
    ]
    if isinstance(instance, dict):
        errs.extend(package_id_errors(instance))
    return errs


def validate_entry(instance: Any, schema: dict | None = None) -> tuple[bool, list[str]]:
    errs = iter_errors(instance, schema)
    return (not errs), errs


def classify_version(ver: dict) -> str:
    life = str(ver.get("lifecycle") or "")
    presence = str(ver.get("presence") or "")
    has_rev = isinstance(ver.get("revocation"), dict)
    has_tom = isinstance(ver.get("tombstone"), dict)
    if life == "revoked" and presence == "retained" and has_rev and not has_tom:
        return "revoked"
    if life == "deleted" and presence == "tombstone" and has_tom and not has_rev:
        return "deleted"
    if life == "deprecated" and presence == "retained" and isinstance(ver.get("deprecation"), dict):
        return "deprecated"
    if life == "published" and presence == "retained" and not has_rev and not has_tom:
        return "published"
    return "unclassified"


def first_version(entry: dict) -> dict:
    vers = entry.get("versions") or []
    if not vers or not isinstance(vers[0], dict):
        return {}
    return vers[0]
