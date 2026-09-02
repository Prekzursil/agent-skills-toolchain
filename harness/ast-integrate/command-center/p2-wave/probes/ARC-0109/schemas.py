#!/usr/bin/env python3
"""Executable JSON Schema fixtures for ARC-0078..ARC-0091.

These are probe-local stand-ins derived from WORK-UNIT-CATALOG question_or_target
text. The loader prefers live command-center/phase4/contracts/<id>.json when that
file exists and is a schema document. This unit does not author those contracts.
"""
from __future__ import annotations

from typing import Any

SCHEMA_META = "https://json-schema.org/draft/2020-12/schema"
CONTRACT_IDS = [f"ARC-{n:04d}" for n in range(78, 92)]


def _obj(
    required: list[str],
    properties: dict[str, Any],
    *,
    additional: bool = False,
    **extra: Any,
) -> dict[str, Any]:
    doc: dict[str, Any] = {
        "type": "object",
        "additionalProperties": additional,
        "required": required,
        "properties": properties,
    }
    doc.update(extra)
    return doc


def _wrap(uid: str, title: str, schema: dict[str, Any]) -> dict[str, Any]:
    out = {
        "$schema": SCHEMA_META,
        "$id": f"ast://phase4/contracts/{uid}",
        "title": title,
        "contract_unit": uid,
    }
    out.update(schema)
    return out


def schema_0078() -> dict[str, Any]:
    return _wrap(
        "ARC-0078",
        "Plugin manifest: interpreter-declared scripts, host compat, zero-hooks reject",
        _obj(
            [
                "name",
                "version",
                "hooks",
                "scripts",
                "host_compat",
                "unknown_field_policy",
            ],
            {
                "name": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 64,
                    "pattern": "^[a-z][a-z0-9-]*$",
                },
                "version": {
                    "type": "string",
                    "pattern": "^[0-9]+\\.[0-9]+\\.[0-9]+$",
                },
                "hooks": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 32,
                    "items": {"type": "string", "minLength": 3, "maxLength": 128},
                },
                "scripts": {
                    "type": "array",
                    "maxItems": 16,
                    "items": _obj(
                        ["path", "interpreter"],
                        {
                            "path": {
                                "type": "string",
                                "minLength": 3,
                                "maxLength": 256,
                            },
                            "interpreter": {
                                "type": "string",
                                "enum": [
                                    "python3",
                                    "node",
                                    "pwsh",
                                    "cmd.exe",
                                    "bash",
                                ],
                            },
                        },
                    ),
                },
                "host_compat": _obj(
                    ["min", "max"],
                    {
                        "min": {"type": "string", "minLength": 1, "maxLength": 32},
                        "max": {"type": "string", "minLength": 1, "maxLength": 32},
                    },
                ),
                "unknown_field_policy": {
                    "type": "string",
                    "enum": ["strict", "tolerant"],
                },
            },
        ),
    )


def schema_0079() -> dict[str, Any]:
    version = _obj(
        ["version", "channel", "lifecycle", "provenance"],
        {
            "version": {"type": "string", "pattern": "^[0-9]+\\.[0-9]+\\.[0-9]+$"},
            "channel": {"type": "string", "enum": ["stable", "beta", "nightly"]},
            "lifecycle": {
                "type": "string",
                "enum": ["active", "deprecated", "revoked"],
            },
            "provenance": _obj(
                ["source_uri", "builder_id"],
                {
                    "source_uri": {"type": "string", "minLength": 8, "maxLength": 256},
                    "builder_id": {"type": "string", "minLength": 3, "maxLength": 64},
                },
            ),
            "signature_ref": {"type": "string", "minLength": 8, "maxLength": 128},
            "sbom_ref": {"type": "string", "minLength": 8, "maxLength": 128},
            "revocation_notice": {
                "type": "string",
                "minLength": 8,
                "maxLength": 256,
            },
        },
    )
    return _wrap(
        "ARC-0079",
        "Marketplace registry entry: provenance, revocation distinct from deletion",
        _obj(
            [
                "package_id",
                "namespace",
                "versions",
                "declared_permissions",
                "license",
                "vulnerability_status",
                "quality_score",
            ],
            {
                "package_id": {
                    "type": "string",
                    "minLength": 3,
                    "maxLength": 64,
                    "pattern": "^[a-z][a-z0-9-]*$",
                },
                "namespace": {
                    "type": "string",
                    "minLength": 2,
                    "maxLength": 32,
                    "pattern": "^[a-z][a-z0-9-]*$",
                },
                "versions": {"type": "array", "minItems": 1, "maxItems": 32, "items": version},
                "declared_permissions": {
                    "type": "array",
                    "minItems": 0,
                    "maxItems": 64,
                    "items": {"type": "string", "minLength": 1, "maxLength": 64},
                },
                "license": {"type": "string", "minLength": 2, "maxLength": 64},
                "vulnerability_status": {
                    "type": "string",
                    "enum": ["clean", "advisory", "blocked"],
                },
                "quality_score": {"type": "integer", "minimum": 0, "maximum": 100},
            },
        ),
    )


def schema_0080() -> dict[str, Any]:
    return _wrap(
        "ARC-0080",
        "Package content boundary, exclusion list, size ceiling, integrity digest",
        _obj(
            [
                "package_id",
                "exclusions",
                "size_ceiling_bytes",
                "integrity_digest",
                "reproducible",
                "on_ceiling_exceeded",
            ],
            {
                "package_id": {"type": "string", "minLength": 3, "maxLength": 64},
                "exclusions": {
                    "type": "array",
                    "minItems": 5,
                    "maxItems": 32,
                    "items": {
                        "type": "string",
                        "enum": [
                            ".git",
                            "caches",
                            "logs",
                            "transcripts",
                            "credentials",
                            "node_modules",
                            "__pycache__",
                        ],
                    },
                    "uniqueItems": True,
                },
                "size_ceiling_bytes": {
                    "type": "integer",
                    "minimum": 1024,
                    "maximum": 104857600,
                },
                "integrity_digest": {
                    "type": "string",
                    "minLength": 64,
                    "maxLength": 64,
                    "pattern": "^[a-f0-9]{64}$",
                },
                "reproducible": {"type": "boolean"},
                "on_ceiling_exceeded": {"type": "string", "enum": ["fail"]},
            },
        ),
    )


def schema_0081() -> dict[str, Any]:
    grant = _obj(
        ["capability_class", "pattern", "effect"],
        {
            "capability_class": {
                "type": "string",
                "enum": [
                    "tool_call",
                    "file_path",
                    "network_egress",
                    "subprocess",
                    "credential_read",
                ],
            },
            "pattern": {"type": "string", "minLength": 1, "maxLength": 128},
            "effect": {"type": "string", "enum": ["grant", "deny"]},
        },
    )
    return _wrap(
        "ARC-0081",
        "Permission vocabulary, evaluation locus, grant/deny, no credential wildcard",
        _obj(
            [
                "evaluation_locus",
                "grants",
                "denies",
                "wildcard_credential_read",
                "least_privilege_statement",
            ],
            {
                "evaluation_locus": {"type": "string", "const": "single-evaluator"},
                "grants": {"type": "array", "minItems": 1, "maxItems": 64, "items": grant},
                "denies": {"type": "array", "maxItems": 64, "items": grant},
                "wildcard_credential_read": {"type": "string", "const": "rejected-at-validation"},
                "least_privilege_statement": {
                    "type": "string",
                    "minLength": 24,
                    "maxLength": 512,
                },
            },
        ),
    )


def schema_0082() -> dict[str, Any]:
    stage = _obj(
        ["id", "kind", "role"],
        {
            "id": {"type": "string", "minLength": 1, "maxLength": 64},
            "kind": {
                "type": "string",
                "enum": ["work", "gate", "checkpoint", "fan-out", "barrier"],
            },
            "role": {"type": "string", "minLength": 1, "maxLength": 32},
            "max_retries": {"type": "integer", "minimum": 0, "maximum": 8},
        },
    )
    return _wrap(
        "ARC-0082",
        "Workflow DSL: stages, gates, resume/replay, certified-executable required set",
        _obj(
            [
                "id",
                "stages",
                "failure_policy",
                "replayable",
                "certified_executable",
                "prompt_transport",
            ],
            {
                "id": {"type": "string", "minLength": 3, "maxLength": 64},
                "stages": {"type": "array", "minItems": 1, "maxItems": 32, "items": stage},
                "failure_policy": {
                    "type": "string",
                    "enum": ["halt", "repair-loop", "skip-stage"],
                },
                "replayable": {"type": "boolean"},
                "certified_executable": {"type": "boolean"},
                "prompt_transport": {"type": "string", "const": "file"},
                "max_cost_usd": {"type": "number", "minimum": 0, "maximum": 10000},
            },
        ),
    )


def schema_0083() -> dict[str, Any]:
    return _wrap(
        "ARC-0083",
        "Work-unit schema: per-unit mandatory fields, closed enums, no defaults-only",
        _obj(
            [
                "id",
                "title",
                "phase",
                "question_or_target",
                "output_path",
                "output_schema",
                "execution_substrate",
                "failure_classification",
                "completion_sentinel",
                "tests_required",
                "evidence_requirement",
                "timeout_seconds",
                "fields_from_global_defaults_only",
            ],
            {
                "id": {"type": "string", "pattern": "^[A-Z]{2,5}-[0-9]{4}$"},
                "title": {"type": "string", "minLength": 8, "maxLength": 200},
                "phase": {"type": "string", "minLength": 1, "maxLength": 8},
                "question_or_target": {
                    "type": "string",
                    "minLength": 40,
                    "maxLength": 4000,
                },
                "output_path": {"type": "string", "minLength": 8, "maxLength": 256},
                "output_schema": {"type": "string", "minLength": 8, "maxLength": 256},
                "execution_substrate": {
                    "type": "string",
                    "enum": [
                        "local-serialized",
                        "local-parallel",
                        "cloud-batch",
                        "worktree-isolated",
                    ],
                },
                "failure_classification": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 16,
                    "items": {
                        "type": "string",
                        "enum": [
                            "detector-failure",
                            "mutation-survives",
                            "schema-invalid",
                            "overclaim",
                            "spec-drift",
                            "docs-code-divergence",
                            "benchmark-gaming",
                        ],
                    },
                },
                "completion_sentinel": {"type": "string", "minLength": 8, "maxLength": 64},
                "tests_required": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 16,
                    "items": {"type": "string", "minLength": 8},
                },
                "evidence_requirement": {
                    "type": "string",
                    "minLength": 16,
                    "maxLength": 2000,
                },
                "timeout_seconds": {
                    "type": "integer",
                    "minimum": 60,
                    "maximum": 86400,
                },
                "fields_from_global_defaults_only": {
                    "type": "array",
                    "maxItems": 0,
                    "items": {"type": "string"},
                },
            },
        ),
    )


def schema_0084() -> dict[str, Any]:
    return _wrap(
        "ARC-0084",
        "Artifact envelope: hash, size floor, schema ref, manifest registration",
        _obj(
            [
                "artifact_id",
                "producing_unit",
                "content_hash",
                "byte_size",
                "schema_ref",
                "sentinel",
                "retention_class",
                "manifest_registered",
            ],
            {
                "artifact_id": {"type": "string", "minLength": 8, "maxLength": 128},
                "producing_unit": {"type": "string", "pattern": "^[A-Z]{2,5}-[0-9]{4}$"},
                "content_hash": {
                    "type": "string",
                    "minLength": 64,
                    "maxLength": 64,
                    "pattern": "^[a-f0-9]{64}$",
                },
                "byte_size": {"type": "integer", "minimum": 2048, "maximum": 104857600},
                "schema_ref": {"type": "string", "minLength": 8, "maxLength": 256},
                "sentinel": {"type": "string", "minLength": 8, "maxLength": 64},
                "retention_class": {
                    "type": "string",
                    "enum": ["ephemeral", "standard", "archival"],
                },
                "manifest_registered": {"type": "boolean", "const": True},
            },
        ),
    )


def schema_0085() -> dict[str, Any]:
    return _wrap(
        "ARC-0085",
        "Claim record: edges, confidence band, settling probe required when unverified",
        _obj(
            [
                "claim_id",
                "mechanism",
                "confidence_band",
                "verification_status",
                "settling_probe",
                "ranking_basis",
            ],
            {
                "claim_id": {"type": "string", "minLength": 8, "maxLength": 64},
                "mechanism": {"type": "string", "minLength": 16, "maxLength": 1000},
                "duplicate_of": {"type": "string", "minLength": 8, "maxLength": 64},
                "support_edges": {
                    "type": "array",
                    "maxItems": 32,
                    "items": {"type": "string", "minLength": 8},
                },
                "contradiction_edges": {
                    "type": "array",
                    "maxItems": 32,
                    "items": {"type": "string", "minLength": 8},
                },
                "confidence_band": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "settled"],
                },
                "verification_status": {
                    "type": "string",
                    "enum": ["UNVERIFIED", "CONFIRMED", "REFUTED"],
                },
                "settling_probe": {"type": "string", "minLength": 8, "maxLength": 256},
                "ranking_basis": {
                    "type": "string",
                    "enum": ["independent-evidence", "decision-impact"],
                },
            },
        ),
    )


def schema_0086() -> dict[str, Any]:
    return _wrap(
        "ARC-0086",
        "Append-only event: monotonic seq, tz timestamp, causality, redaction",
        _obj(
            [
                "seq",
                "timestamp",
                "actor",
                "unit_id",
                "phase",
                "state_transition",
                "correlation_id",
                "causality_id",
                "payload_digest",
                "secret_redacted",
            ],
            {
                "seq": {"type": "integer", "minimum": 0, "maximum": 1000000000},
                "timestamp": {
                    "type": "string",
                    "minLength": 20,
                    "maxLength": 40,
                    "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}T",
                },
                "actor": {"type": "string", "minLength": 2, "maxLength": 64},
                "unit_id": {"type": "string", "pattern": "^[A-Z]{2,5}-[0-9]{4}$"},
                "phase": {"type": "string", "minLength": 1, "maxLength": 16},
                "state_transition": {
                    "type": "string",
                    "enum": ["queued", "running", "success", "failed", "blocked"],
                },
                "correlation_id": {"type": "string", "minLength": 8, "maxLength": 64},
                "causality_id": {"type": "string", "minLength": 8, "maxLength": 64},
                "payload_digest": {
                    "type": "string",
                    "minLength": 64,
                    "maxLength": 64,
                    "pattern": "^[a-f0-9]{64}$",
                },
                "secret_redacted": {"type": "boolean", "const": True},
            },
        ),
    )


def schema_0087() -> dict[str, Any]:
    cond = _obj(
        ["id", "status", "applicable"],
        {
            "id": {"type": "integer", "minimum": 1, "maximum": 12},
            "status": {
                "type": "string",
                "enum": ["PASS", "FAIL", "N/A", "UNKNOWN"],
            },
            "applicable": {"type": "boolean"},
        },
    )
    return _wrap(
        "ARC-0087",
        "Completion predicate: twelve conditions, UNKNOWN != FALSE, exit-0 is not success",
        _obj(
            [
                "unit_id",
                "conditions",
                "exit_code",
                "exit_zero_is_success",
                "overall",
            ],
            {
                "unit_id": {"type": "string", "pattern": "^[A-Z]{2,5}-[0-9]{4}$"},
                "conditions": {
                    "type": "array",
                    "minItems": 12,
                    "maxItems": 12,
                    "items": cond,
                },
                "exit_code": {"type": "integer", "minimum": 0, "maximum": 255},
                "exit_zero_is_success": {"type": "boolean", "const": False},
                "overall": {
                    "type": "string",
                    "enum": ["PASS", "FAIL", "UNKNOWN"],
                },
            },
        ),
    )


def schema_0088() -> dict[str, Any]:
    return _wrap(
        "ARC-0088",
        "Hook contract: stdin JSON, exit 2 danger-only, fail-open, wiring proof",
        _obj(
            [
                "event",
                "timeout_ms",
                "fail_open_on_internal_error",
                "exit_code_policy",
                "wired",
                "wiring_proof",
            ],
            {
                "event": {
                    "type": "string",
                    "enum": [
                        "PreToolUse",
                        "PostToolUse",
                        "Stop",
                        "SessionStart",
                        "UserPromptSubmit",
                    ],
                },
                "timeout_ms": {"type": "integer", "minimum": 50, "maximum": 30000},
                "fail_open_on_internal_error": {"type": "boolean", "const": True},
                "exit_code_policy": _obj(
                    ["block_reserved_for"],
                    {
                        "block_reserved_for": {
                            "type": "string",
                            "const": "irreversible-danger",
                        },
                        "guidance_exit": {"type": "integer", "enum": [0, 1]},
                    },
                ),
                "wired": {"type": "boolean", "const": True},
                "wiring_proof": _obj(
                    ["dispatcher_record", "external_side_effect"],
                    {
                        "dispatcher_record": {
                            "type": "string",
                            "minLength": 8,
                            "maxLength": 256,
                        },
                        "external_side_effect": {
                            "type": "string",
                            "minLength": 8,
                            "maxLength": 256,
                        },
                    },
                ),
            },
        ),
    )


def schema_0089() -> dict[str, Any]:
    return _wrap(
        "ARC-0089",
        "Skill contract: package shape, router description, always-on vs lazy, deploy parity",
        _obj(
            [
                "skill_id",
                "relative_path",
                "description",
                "load_semantics",
                "load_field",
                "repo_present",
                "live_present",
            ],
            {
                "skill_id": {
                    "type": "string",
                    "minLength": 3,
                    "maxLength": 64,
                    "pattern": "^[a-z][a-z0-9._-]*$",
                },
                "relative_path": {
                    "type": "string",
                    "minLength": 8,
                    "maxLength": 256,
                },
                "description": {"type": "string", "minLength": 16, "maxLength": 500},
                "load_semantics": {
                    "type": "string",
                    "enum": ["always-on", "lazy"],
                },
                "load_field": {"type": "string", "minLength": 3, "maxLength": 64},
                "repo_present": {"type": "boolean"},
                "live_present": {"type": "boolean"},
            },
        ),
    )


def schema_0090() -> dict[str, Any]:
    return _wrap(
        "ARC-0090",
        "MCP adapter: transport, lifecycle owner, process cap, namespacing, enable scope",
        _obj(
            [
                "server_id",
                "transport",
                "lifecycle_owner",
                "max_processes_per_session",
                "tool_namespace",
                "enable_scope",
            ],
            {
                "server_id": {
                    "type": "string",
                    "minLength": 3,
                    "maxLength": 64,
                    "pattern": "^[a-z][a-z0-9._-]*$",
                },
                "transport": {"type": "string", "enum": ["stdio", "http"]},
                "lifecycle_owner": {
                    "type": "string",
                    "enum": ["session", "shared-supervisor"],
                },
                "max_processes_per_session": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 8,
                },
                "tool_namespace": {"type": "string", "minLength": 2, "maxLength": 32},
                "enable_scope": {
                    "type": "string",
                    "enum": ["user", "project", "local", "session"],
                },
                "enable_effective": {"type": "boolean"},
            },
        ),
    )


def schema_0091() -> dict[str, Any]:
    return _wrap(
        "ARC-0091",
        "Cross-vendor adapter: negotiation, leak declaration mandatory, file prompt transport",
        _obj(
            [
                "vendor",
                "tier",
                "abstraction_leaks",
                "prompt_transport",
                "blocking_dispatch",
                "terminal_state_marker",
            ],
            {
                "vendor": {"type": "string", "minLength": 2, "maxLength": 32},
                "tier": {
                    "type": "string",
                    "enum": ["guaranteed", "best-effort", "vendor-only"],
                },
                "abstraction_leaks": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 32,
                    "items": {"type": "string", "minLength": 8, "maxLength": 256},
                },
                "prompt_transport": {"type": "string", "const": "file"},
                "blocking_dispatch": {"type": "boolean", "const": True},
                "terminal_state_marker": {
                    "type": "string",
                    "minLength": 8,
                    "maxLength": 64,
                },
            },
        ),
    )


BUILDERS = {
    "ARC-0078": schema_0078,
    "ARC-0079": schema_0079,
    "ARC-0080": schema_0080,
    "ARC-0081": schema_0081,
    "ARC-0082": schema_0082,
    "ARC-0083": schema_0083,
    "ARC-0084": schema_0084,
    "ARC-0085": schema_0085,
    "ARC-0086": schema_0086,
    "ARC-0087": schema_0087,
    "ARC-0088": schema_0088,
    "ARC-0089": schema_0089,
    "ARC-0090": schema_0090,
    "ARC-0091": schema_0091,
}


def fixture_schema(uid: str) -> dict[str, Any]:
    return BUILDERS[uid]()
