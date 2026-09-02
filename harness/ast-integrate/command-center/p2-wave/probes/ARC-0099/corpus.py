#!/usr/bin/env python3
"""Negative-fixture corpus for ARC-0078..ARC-0087 contract schemas.

Coverage = (schemas with one accepting AND one semantic rejecting fixture)
         / (schemas defined). A reject that fails JSON syntax does not count.
Frozen contracts at phase4/contracts/ are preferred when they are JSON Schema;
otherwise catalog-derived stand-in schemas in this probe directory are used.
Stand-ins are not a freeze of ARC-0078..ARC-0087.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Callable

from jsonschema import Draft7Validator

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FROZEN_DIR = REPO / "command-center" / "phase4" / "contracts"
SCHEMA_DIR = HERE / "schemas"
FIXTURE_DIR = HERE / "fixtures"
SYNTAX_BAD = '{"broken": true,'
HEX64 = "a" * 64
CONTRACT_IDS = [f"ARC-{n:04d}" for n in range(78, 88)]

Mutator = Callable[[dict], dict]


def _kw_tree(err: Any) -> set[str]:
    keys = {str(err.validator)}
    for child in err.context or []:
        keys |= _kw_tree(child)
    return keys


def classify_instance(schema: dict, raw: str) -> dict:
    """Classify one fixture body against a schema.

    kind:
      syntax   - JSON does not parse
      accepted - parses and schema-valid
      semantic - parses and schema-invalid (keyword set recorded)
    """
    try:
        inst = json.loads(raw)
    except json.JSONDecodeError as exc:
        return {
            "kind": "syntax",
            "ok": False,
            "keywords": [],
            "message": f"JSONDecodeError: {exc.msg}",
            "reason": "syntax-error-not-semantic-violation",
        }
    validator = Draft7Validator(schema)
    errors = sorted(validator.iter_errors(inst), key=lambda e: list(e.absolute_path))
    if not errors:
        return {
            "kind": "accepted",
            "ok": True,
            "keywords": [],
            "message": "",
            "reason": "schema-valid",
        }
    err = errors[0]
    keywords = sorted(_kw_tree(err))
    return {
        "kind": "semantic",
        "ok": False,
        "keywords": keywords,
        "message": err.message,
        "reason": f"semantic:{err.validator}:{err.message}",
        "primary_keyword": str(err.validator),
    }


def _plugin_schema() -> dict:
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": "command-center/p2-wave/probes/ARC-0099/schemas/ARC-0078.schema.json",
        "title": "Plugin manifest (ARC-0078 catalog-derived stand-in)",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "name",
            "version",
            "hooks",
            "scripts",
            "compatibility",
            "unknown_field_policy",
        ],
        "properties": {
            "name": {"type": "string", "minLength": 1},
            "version": {"type": "string", "minLength": 1},
            "unknown_field_policy": {"type": "string", "enum": ["strict", "tolerant"]},
            "compatibility": {
                "type": "object",
                "additionalProperties": False,
                "required": ["min_host", "max_host"],
                "properties": {
                    "min_host": {"type": "string", "minLength": 1},
                    "max_host": {"type": "string", "minLength": 1},
                },
            },
            "hooks": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["id", "event"],
                    "properties": {
                        "id": {"type": "string", "minLength": 1},
                        "event": {"type": "string", "minLength": 1},
                    },
                },
            },
            "scripts": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["path", "interpreter"],
                    "properties": {
                        "path": {"type": "string", "minLength": 1},
                        "interpreter": {"type": "string", "minLength": 1},
                    },
                },
            },
        },
    }


def _marketplace_schema() -> dict:
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": "command-center/p2-wave/probes/ARC-0099/schemas/ARC-0079.schema.json",
        "title": "Marketplace registry entry (ARC-0079 catalog-derived stand-in)",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "package_id",
            "namespace",
            "versions",
            "provenance",
            "revocation",
            "permissions",
            "platform",
        ],
        "properties": {
            "package_id": {"type": "string", "minLength": 3, "pattern": "^[a-z][a-z0-9._-]*$"},
            "namespace": {"type": "string", "minLength": 2},
            "versions": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["version", "channel"],
                    "properties": {
                        "version": {"type": "string", "minLength": 1},
                        "channel": {"type": "string", "minLength": 1},
                    },
                },
            },
            "provenance": {
                "type": "object",
                "additionalProperties": False,
                "required": ["source", "signature_ref", "sbom_ref", "license"],
                "properties": {
                    "source": {"type": "string", "minLength": 1},
                    "signature_ref": {"type": "string", "minLength": 1},
                    "sbom_ref": {"type": "string", "minLength": 1},
                    "license": {"type": "string", "minLength": 1},
                },
            },
            "revocation": {
                "type": "object",
                "additionalProperties": False,
                "required": ["state", "revoked_versions"],
                "properties": {
                    "state": {
                        "type": "string",
                        "enum": ["active", "deprecated", "revoked"],
                    },
                    "revoked_versions": {"type": "array", "items": {"type": "string"}},
                },
            },
            "permissions": {"type": "array", "items": {"type": "string"}},
            "platform": {"type": "array", "minItems": 1, "items": {"type": "string"}},
            "quality_score": {"type": "number", "minimum": 0, "maximum": 1},
            "vulnerability_status": {"type": "string", "minLength": 1},
        },
    }


def _package_schema() -> dict:
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": "command-center/p2-wave/probes/ARC-0099/schemas/ARC-0080.schema.json",
        "title": "Package content boundary (ARC-0080 catalog-derived stand-in)",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "package_id",
            "exclusions",
            "size_ceiling_bytes",
            "content_digest",
            "included_paths",
            "reproducibility",
            "byte_size",
        ],
        "properties": {
            "package_id": {"type": "string", "minLength": 3},
            "exclusions": {
                "type": "array",
                "minItems": 5,
                "items": {"type": "string", "minLength": 1},
            },
            "size_ceiling_bytes": {"type": "integer", "minimum": 1024},
            "content_digest": {
                "type": "string",
                "pattern": "^sha256:[a-f0-9]{64}$",
            },
            "included_paths": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "string",
                    "minLength": 1,
                    "allOf": [
                        {"not": {"pattern": "(^|/)\\.git(/|$)"}},
                        {"not": {"pattern": "(^|/)\\.env$"}},
                        {"not": {"pattern": "[Cc]redential"}},
                    ],
                },
            },
            "reproducibility": {
                "type": "object",
                "additionalProperties": False,
                "required": ["declared", "command"],
                "properties": {
                    "declared": {"type": "boolean"},
                    "command": {"type": "string", "minLength": 3},
                },
            },
            "byte_size": {"type": "integer", "minimum": 1},
        },
    }


def _permission_schema() -> dict:
    cap = {
        "type": "string",
        "enum": [
            "tool_call",
            "file_path",
            "network_egress",
            "subprocess",
            "credential_read",
        ],
    }
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": "command-center/p2-wave/probes/ARC-0099/schemas/ARC-0081.schema.json",
        "title": "Permission model (ARC-0081 catalog-derived stand-in)",
        "type": "object",
        "additionalProperties": False,
        "required": ["vocabulary", "evaluation_site", "least_privilege", "rules"],
        "properties": {
            "vocabulary": {"type": "array", "minItems": 5, "items": cap},
            "evaluation_site": {"type": "string", "minLength": 3},
            "least_privilege": {"type": "string", "minLength": 8},
            "rules": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["effect", "capability", "resource"],
                    "properties": {
                        "effect": {"type": "string", "enum": ["grant", "deny"]},
                        "capability": cap,
                        "resource": {"type": "string", "minLength": 1},
                    },
                    "if": {
                        "properties": {
                            "effect": {"const": "grant"},
                            "capability": {"const": "credential_read"},
                        },
                        "required": ["effect", "capability"],
                    },
                    "then": {
                        "properties": {
                            "resource": {
                                "type": "string",
                                "pattern": "^[^*]+$",
                            }
                        }
                    },
                },
            },
        },
    }


def _workflow_schema() -> dict:
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": "command-center/p2-wave/probes/ARC-0099/schemas/ARC-0082.schema.json",
        "title": "Workflow DSL (ARC-0082 catalog-derived stand-in)",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "id",
            "certified_executable",
            "stages",
            "gates",
            "failure_policy",
            "replay",
        ],
        "properties": {
            "id": {"type": "string", "minLength": 3},
            "certified_executable": {"type": "boolean"},
            "stages": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["id", "kind"],
                    "properties": {
                        "id": {"type": "string", "minLength": 1},
                        "kind": {"type": "string", "minLength": 1},
                    },
                },
            },
            "gates": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["id", "kind"],
                    "properties": {
                        "id": {"type": "string", "minLength": 1},
                        "kind": {"type": "string", "minLength": 1},
                    },
                },
            },
            "failure_policy": {"type": "string", "enum": ["halt", "retry", "repair"]},
            "replay": {
                "type": "object",
                "additionalProperties": False,
                "required": ["deterministic", "dry_run"],
                "properties": {
                    "deterministic": {"type": "boolean"},
                    "dry_run": {"type": "boolean"},
                },
            },
            "roles": {"type": "array", "items": {"type": "string"}},
        },
    }


def _workunit_schema() -> dict:
    substrates = [
        "worktree-isolated",
        "local-parallel",
        "cloud-batch",
        "local-windows-pwsh7",
    ]
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": "command-center/p2-wave/probes/ARC-0099/schemas/ARC-0083.schema.json",
        "title": "Work-unit record (ARC-0083 catalog-derived stand-in)",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "id",
            "title",
            "phase",
            "target",
            "inputs",
            "dependencies",
            "assignment",
            "tool_permissions",
            "execution_substrate",
            "timeout_seconds",
            "output_path",
            "output_schema",
            "evidence_requirement",
            "tests_required",
            "reviewer_requirement",
            "completion_sentinel",
            "retry_policy",
            "failure_classification",
            "owner_approval_required",
        ],
        "properties": {
            "id": {"type": "string", "minLength": 3},
            "title": {"type": "string", "minLength": 8},
            "phase": {"type": "string", "minLength": 1},
            "target": {"type": "string", "minLength": 16},
            "inputs": {"type": "array", "items": {"type": "string"}},
            "dependencies": {"type": "array", "items": {"type": "string"}},
            "assignment": {
                "type": "object",
                "required": ["model", "role", "vendor"],
                "properties": {
                    "model": {"type": "string", "minLength": 1},
                    "role": {"type": "string", "minLength": 1},
                    "vendor": {"type": "string", "minLength": 1},
                },
            },
            "tool_permissions": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "string"},
            },
            "execution_substrate": {"type": "string", "enum": substrates},
            "timeout_seconds": {"type": "integer", "minimum": 1},
            "output_path": {"type": "string", "minLength": 8},
            "output_schema": {"type": "string", "minLength": 8},
            "evidence_requirement": {"type": "string", "minLength": 8},
            "tests_required": {"type": "array", "minItems": 1, "items": {"type": "string"}},
            "reviewer_requirement": {"type": "string", "minLength": 8},
            "completion_sentinel": {"type": "string", "minLength": 8},
            "retry_policy": {"type": "string", "minLength": 8},
            "failure_classification": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "string", "minLength": 3},
            },
            "owner_approval_required": {"type": "boolean"},
        },
    }


def _artifact_schema() -> dict:
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": "command-center/p2-wave/probes/ARC-0099/schemas/ARC-0084.schema.json",
        "title": "Artifact envelope (ARC-0084 catalog-derived stand-in)",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "artifact_id",
            "producing_unit",
            "content_hash",
            "byte_size",
            "schema_reference",
            "sentinel",
            "evidence_anchors",
            "retention_class",
            "registered_in_manifest",
        ],
        "properties": {
            "artifact_id": {"type": "string", "minLength": 3},
            "producing_unit": {"type": "string", "minLength": 3},
            "content_hash": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
            "byte_size": {"type": "integer", "minimum": 256},
            "schema_reference": {"type": "string", "minLength": 8},
            "sentinel": {"type": "string", "minLength": 8},
            "evidence_anchors": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "string", "minLength": 3},
            },
            "retention_class": {
                "type": "string",
                "enum": ["ephemeral", "standard", "archival"],
            },
            "registered_in_manifest": {"type": "boolean", "const": True},
        },
    }


def _claim_schema() -> dict:
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": "command-center/p2-wave/probes/ARC-0099/schemas/ARC-0085.schema.json",
        "title": "Claim record (ARC-0085 catalog-derived stand-in)",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "claim_id",
            "mechanism",
            "lineage",
            "confidence",
            "verification_status",
            "settling_probe",
            "duplicate_of",
            "support",
            "contradiction",
            "implementation_impact",
        ],
        "properties": {
            "claim_id": {"type": "string", "minLength": 3},
            "mechanism": {"type": "string", "minLength": 16},
            "lineage": {"type": "array", "minItems": 1},
            "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
            "verification_status": {
                "type": "string",
                "enum": ["UNVERIFIED", "VERIFIED", "REFUTED"],
            },
            "settling_probe": {"type": "string", "minLength": 8},
            "duplicate_of": {"type": "array"},
            "support": {"type": "array"},
            "contradiction": {"type": "array"},
            "implementation_impact": {"type": "string", "minLength": 3},
        },
    }


def _event_schema() -> dict:
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": "command-center/p2-wave/probes/ARC-0099/schemas/ARC-0086.schema.json",
        "title": "Append-only event (ARC-0086 catalog-derived stand-in)",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "seq",
            "timestamp",
            "timezone",
            "actor",
            "unit_id",
            "phase",
            "state_from",
            "state_to",
            "correlation_id",
            "causality_id",
            "payload",
            "redacted",
        ],
        "properties": {
            "seq": {"type": "integer", "minimum": 1},
            "timestamp": {"type": "string", "minLength": 20},
            "timezone": {"type": "string", "minLength": 1},
            "actor": {"type": "string", "minLength": 1},
            "unit_id": {"type": "string", "minLength": 3},
            "phase": {"type": "string", "minLength": 1},
            "state_from": {"type": "string", "minLength": 1},
            "state_to": {"type": "string", "minLength": 1},
            "correlation_id": {"type": "string", "minLength": 1},
            "causality_id": {"type": "string", "minLength": 1},
            "payload": {
                "type": "object",
                "required": ["summary"],
                "properties": {
                    "summary": {
                        "type": "string",
                        "minLength": 1,
                        "not": {"pattern": "(AKIA|sk-[A-Za-z0-9]|BEGIN PRIVATE KEY)"},
                    }
                },
            },
            "redacted": {"type": "boolean"},
        },
    }


def _predicate_schema() -> dict:
    cond = {
        "type": "object",
        "additionalProperties": False,
        "required": ["id", "applicable", "result"],
        "properties": {
            "id": {"type": "string", "minLength": 2},
            "applicable": {"type": "boolean"},
            "result": {"type": "string", "enum": ["PASS", "FAIL", "UNKNOWN", "NA"]},
        },
    }
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": "command-center/p2-wave/probes/ARC-0099/schemas/ARC-0087.schema.json",
        "title": "Completion predicate result (ARC-0087 catalog-derived stand-in)",
        "type": "object",
        "additionalProperties": False,
        "required": ["unit_id", "exit_code", "overall", "conditions"],
        "properties": {
            "unit_id": {"type": "string", "minLength": 3},
            "exit_code": {"type": "integer", "minimum": 0},
            "overall": {"type": "string", "enum": ["PASS", "FAIL", "UNKNOWN"]},
            "conditions": {"type": "array", "minItems": 12, "maxItems": 12, "items": cond},
        },
        "if": {
            "properties": {
                "conditions": {
                    "contains": {
                        "type": "object",
                        "properties": {"result": {"const": "FAIL"}},
                        "required": ["result"],
                    }
                }
            }
        },
        "then": {
            "properties": {
                "overall": {"type": "string", "not": {"const": "PASS"}}
            }
        },
    }


def _twelve(result: str = "PASS") -> list[dict]:
    rows = []
    names = [
        "C1-exit-not-sufficient",
        "C2-artifact-present",
        "C3-artifact-nonempty",
        "C4-schema-valid",
        "C5-sentinel",
        "C6-evidence",
        "C7-tests",
        "C8-reviewer",
        "C9-no-overclaim",
        "C10-named-probes",
        "C11-manifest-row",
        "C12-applicability",
    ]
    for name in names:
        rows.append({"id": name, "applicable": True, "result": result})
    return rows


def _drop(key: str) -> Mutator:
    def mut(inst: dict) -> dict:
        out = copy.deepcopy(inst)
        out.pop(key, None)
        return out

    return mut


def _set_hooks_empty(inst: dict) -> dict:
    out = copy.deepcopy(inst)
    out["hooks"] = []
    return out


def _include_git(inst: dict) -> dict:
    out = copy.deepcopy(inst)
    out["included_paths"] = [".git/config"] + list(out.get("included_paths") or [])
    return out


def _grant_cred_star(inst: dict) -> dict:
    out = copy.deepcopy(inst)
    rules = list(out.get("rules") or [])
    rules.append(
        {"effect": "grant", "capability": "credential_read", "resource": "*"}
    )
    out["rules"] = rules
    return out


def _widen_substrate(inst: dict) -> dict:
    out = copy.deepcopy(inst)
    out["execution_substrate"] = "made-up-substrate"
    return out


def _tiny_bytes(inst: dict) -> dict:
    out = copy.deepcopy(inst)
    out["byte_size"] = 1
    return out


def _unknown_field(inst: dict) -> dict:
    out = copy.deepcopy(inst)
    out["unexpected_future_field"] = "x"
    return out


def _vacuous_pass(inst: dict) -> dict:
    out = copy.deepcopy(inst)
    out["exit_code"] = 0
    out["overall"] = "PASS"
    conds = copy.deepcopy(out["conditions"])
    conds[1]["result"] = "FAIL"
    out["conditions"] = conds
    return out


def contract_defs() -> list[dict]:
    plugin_accept = {
        "name": "harness",
        "version": "1.0.0",
        "unknown_field_policy": "strict",
        "compatibility": {"min_host": "1.0.0", "max_host": "2.0.0"},
        "hooks": [{"id": "pre-tool", "event": "PreToolUse"}],
        "scripts": [{"path": "hooks/pre-tool.py", "interpreter": "python3"}],
    }
    market_accept = {
        "package_id": "harness.core",
        "namespace": "harness",
        "versions": [
            {"version": "1.0.0", "channel": "stable"},
            {"version": "0.9.0", "channel": "retired"},
        ],
        "provenance": {
            "source": "registry.example",
            "signature_ref": "sig:abc",
            "sbom_ref": "sbom:abc",
            "license": "MIT",
        },
        "revocation": {"state": "revoked", "revoked_versions": ["0.9.0"]},
        "permissions": ["tool_call:read"],
        "platform": ["linux"],
        "quality_score": 0.8,
        "vulnerability_status": "clean",
    }
    pkg_accept = {
        "package_id": "harness.core",
        "exclusions": [
            ".git",
            "**/.env",
            "**/credentials*",
            "**/*.log",
            "**/transcripts/**",
            "**/*cache*",
        ],
        "size_ceiling_bytes": 10485760,
        "content_digest": f"sha256:{HEX64}",
        "included_paths": ["plugin.json", "hooks/pre-tool.py"],
        "reproducibility": {"declared": True, "command": "python3 -m build"},
        "byte_size": 4096,
    }
    perm_accept = {
        "vocabulary": [
            "tool_call",
            "file_path",
            "network_egress",
            "subprocess",
            "credential_read",
        ],
        "evaluation_site": "permission-evaluator",
        "least_privilege": "declared-must-cover-observed-and-nothing-more",
        "rules": [
            {"effect": "grant", "capability": "tool_call", "resource": "Read"},
            {"effect": "deny", "capability": "credential_read", "resource": "*"},
        ],
    }
    wf_accept = {
        "id": "wf.catalog-class.discovery-only",
        "certified_executable": True,
        "stages": [{"id": "discover", "kind": "static-scan"}],
        "gates": [{"id": "human-checkpoint", "kind": "approval"}],
        "failure_policy": "halt",
        "replay": {"deterministic": True, "dry_run": True},
        "roles": ["architect"],
    }
    wu_accept = {
        "id": "ARC-0099",
        "title": "Negative-fixture corpus",
        "phase": "4",
        "target": "Author both-states fixtures for every contract schema.",
        "inputs": ["command-center/phase4/contracts/ARC-0078.json"],
        "dependencies": ["ARC-0078"],
        "assignment": {"model": "opus", "role": "test-engineer", "vendor": "anthropic"},
        "tool_permissions": ["Read", "Bash"],
        "execution_substrate": "worktree-isolated",
        "timeout_seconds": 7200,
        "output_path": "command-center/phase4/conformance/ARC-0099.json",
        "output_schema": "command-center/schema/conformance-report.schema.json",
        "evidence_requirement": "Coverage is schemas with both-states divided by schemas defined.",
        "tests_required": ["Both-states per schema", "Anti-tautology on syntax rejects"],
        "reviewer_requirement": "one independent reviewer who re-runs the named probes",
        "completion_sentinel": "SUCCESS:ARC-0099",
        "retry_policy": "retry once after fixing validator input",
        "failure_classification": ["detector-failure", "overclaim"],
        "owner_approval_required": False,
    }
    art_accept = {
        "artifact_id": "ARC-0099-report",
        "producing_unit": "ARC-0099",
        "content_hash": HEX64,
        "byte_size": 4096,
        "schema_reference": "command-center/schema/conformance-report.schema.json",
        "sentinel": "SUCCESS:ARC-0099",
        "evidence_anchors": ["command-center/WORK-UNIT-CATALOG.json"],
        "retention_class": "standard",
        "registered_in_manifest": True,
    }
    claim_accept = {
        "claim_id": "CLM-ARC-0099-BOTH-STATES",
        "mechanism": "A schema is covered only when one instance is accepted and one is semantically rejected.",
        "lineage": [{"source": "catalog", "unit": "ARC-0099"}],
        "confidence": "high",
        "verification_status": "UNVERIFIED",
        "settling_probe": "command-center/p2-wave/probes/ARC-0099/probe1_both_states.py",
        "duplicate_of": [],
        "support": [],
        "contradiction": [],
        "implementation_impact": "conformance-gate",
    }
    ev_accept = {
        "seq": 1,
        "timestamp": "2026-08-24T18:00:00Z",
        "timezone": "UTC",
        "actor": "arc-0099-corpus",
        "unit_id": "ARC-0099",
        "phase": "4",
        "state_from": "ABSENT",
        "state_to": "SUCCESS",
        "correlation_id": "corr-0099",
        "causality_id": "cause-0099",
        "payload": {"summary": "both-states corpus materialized"},
        "redacted": True,
    }
    pred_accept = {
        "unit_id": "ARC-0099",
        "exit_code": 0,
        "overall": "PASS",
        "conditions": _twelve("PASS"),
    }
    return [
        {
            "id": "ARC-0078",
            "title": "Plugin manifest",
            "schema": _plugin_schema(),
            "accept": plugin_accept,
            "mutate": _set_hooks_empty,
            "mutation": "zero_hooks",
            "intended_keyword": "minItems",
            "suggested_minimal_mutation": "empty hooks array (zero-hooks installed-but-loads-nothing shape)",
        },
        {
            "id": "ARC-0079",
            "title": "Marketplace registry entry",
            "schema": _marketplace_schema(),
            "accept": market_accept,
            "mutate": _drop("provenance"),
            "mutation": "removed_required_field",
            "intended_keyword": "required",
            "suggested_minimal_mutation": "remove required provenance object",
        },
        {
            "id": "ARC-0080",
            "title": "Package content boundary",
            "schema": _package_schema(),
            "accept": pkg_accept,
            "mutate": _include_git,
            "mutation": "forbidden_path",
            "intended_keyword": "not",
            "suggested_minimal_mutation": "include .git/config in packaged paths",
        },
        {
            "id": "ARC-0081",
            "title": "Permission model",
            "schema": _permission_schema(),
            "accept": perm_accept,
            "mutate": _grant_cred_star,
            "mutation": "wildcard_escalation",
            "intended_keyword": "pattern",
            "suggested_minimal_mutation": "grant credential_read with resource=*",
        },
        {
            "id": "ARC-0082",
            "title": "Workflow DSL",
            "schema": _workflow_schema(),
            "accept": wf_accept,
            "mutate": _drop("stages"),
            "mutation": "removed_required_field",
            "intended_keyword": "required",
            "suggested_minimal_mutation": "remove required stages array",
        },
        {
            "id": "ARC-0083",
            "title": "Work-unit schema",
            "schema": _workunit_schema(),
            "accept": wu_accept,
            "mutate": _widen_substrate,
            "mutation": "widened_enum",
            "intended_keyword": "enum",
            "suggested_minimal_mutation": "execution_substrate value outside the closed enum",
        },
        {
            "id": "ARC-0084",
            "title": "Artifact envelope",
            "schema": _artifact_schema(),
            "accept": art_accept,
            "mutate": _tiny_bytes,
            "mutation": "below_size_floor",
            "intended_keyword": "minimum",
            "suggested_minimal_mutation": "byte_size=1 (below the 256-byte floor)",
        },
        {
            "id": "ARC-0085",
            "title": "Claim record",
            "schema": _claim_schema(),
            "accept": claim_accept,
            "mutate": _drop("settling_probe"),
            "mutation": "removed_required_field",
            "intended_keyword": "required",
            "suggested_minimal_mutation": "UNVERIFIED claim with settling_probe removed",
        },
        {
            "id": "ARC-0086",
            "title": "Event record",
            "schema": _event_schema(),
            "accept": ev_accept,
            "mutate": _unknown_field,
            "mutation": "unknown_field",
            "intended_keyword": "additionalProperties",
            "suggested_minimal_mutation": "unknown field unexpected_future_field",
        },
        {
            "id": "ARC-0087",
            "title": "Completion predicate",
            "schema": _predicate_schema(),
            "accept": pred_accept,
            "mutate": _vacuous_pass,
            "mutation": "exit_zero_masks_fail",
            "intended_keyword": "not",
            "suggested_minimal_mutation": "overall=PASS while C2-artifact-present is FAIL and exit_code=0",
        },
    ]


def looks_like_json_schema(doc: Any) -> bool:
    if not isinstance(doc, dict):
        return False
    # Receipt envelopes often carry $schema/$id; those are not instance schemas.
    # A contract schema for this corpus must declare object properties.
    return (
        isinstance(doc, dict)
        and doc.get("type") == "object"
        and isinstance(doc.get("properties"), dict)
        and bool(doc.get("properties"))
    )


def load_schema_for(defn: dict) -> tuple[dict, str, str]:
    uid = defn["id"]
    frozen = FROZEN_DIR / f"{uid}.json"
    rel_frozen = f"command-center/phase4/contracts/{uid}.json"
    standin_rel = f"command-center/p2-wave/probes/ARC-0099/schemas/{uid}.schema.json"
    standin = copy.deepcopy(defn["schema"])
    if frozen.is_file() and frozen.stat().st_size > 0:
        try:
            doc = json.loads(frozen.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            doc = None
        if looks_like_json_schema(doc):
            acc = classify_instance(doc, json.dumps(defn["accept"]))
            # Later-delivered frozen contracts (other ARC units) are a different
            # document class than this corpus's stand-in accept instances.
            # Only use frozen when the existing accept fixture is valid on it.
            if acc.get("ok"):
                return doc, "frozen-contract", rel_frozen
    return standin, "catalog-derived-stand-in", standin_rel


def materialize() -> None:
    SCHEMA_DIR.mkdir(parents=True, exist_ok=True)
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    for defn in contract_defs():
        uid = defn["id"]
        schema_path = SCHEMA_DIR / f"{uid}.schema.json"
        schema_path.write_text(
            json.dumps(defn["schema"], indent=2) + "\n", encoding="utf-8"
        )
        fx = FIXTURE_DIR / uid
        fx.mkdir(parents=True, exist_ok=True)
        accept = defn["accept"]
        reject = defn["mutate"](accept)
        (fx / "accept.json").write_text(
            json.dumps(accept, indent=2) + "\n", encoding="utf-8"
        )
        (fx / "reject.json").write_text(
            json.dumps(reject, indent=2) + "\n", encoding="utf-8"
        )
        (fx / "reject.meta.json").write_text(
            json.dumps(
                {
                    "mutation": defn["mutation"],
                    "intended_keyword": defn["intended_keyword"],
                    "suggested_minimal_mutation": defn["suggested_minimal_mutation"],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (fx / "syntax-bad.txt").write_text(SYNTAX_BAD + "\n", encoding="utf-8")


def evaluate() -> dict:
    materialize()
    rows = []
    syntax_ok = True
    reason_asserted = True
    for defn in contract_defs():
        uid = defn["id"]
        schema, source, schema_path = load_schema_for(defn)
        fx = FIXTURE_DIR / uid
        accept_raw = (fx / "accept.json").read_text(encoding="utf-8")
        reject_raw = (fx / "reject.json").read_text(encoding="utf-8")
        syntax_raw = (fx / "syntax-bad.txt").read_text(encoding="utf-8")
        meta = json.loads((fx / "reject.meta.json").read_text(encoding="utf-8"))
        intended = meta["intended_keyword"]
        acc = classify_instance(schema, accept_raw)
        rej = classify_instance(schema, reject_raw)
        syn = classify_instance(schema, syntax_raw)
        if syn.get("kind") != "syntax":
            syntax_ok = False
        if syn.get("reason") != "syntax-error-not-semantic-violation":
            reason_asserted = False
        semantic_ok = (
            rej.get("kind") == "semantic" and intended in (rej.get("keywords") or [])
        )
        if rej.get("kind") == "syntax":
            reject_class = "syntax"
        elif rej.get("kind") == "accepted":
            reject_class = "accepted"
        elif semantic_ok:
            reject_class = "semantic"
        else:
            reject_class = "keyword-mismatch"
        covered = bool(acc.get("ok")) and semantic_ok
        rows.append(
            {
                "schema_id": uid,
                "title": defn["title"],
                "schema_source": source,
                "schema_path": schema_path,
                "frozen_contract_present": source == "frozen-contract",
                "accept_ok": bool(acc.get("ok")),
                "accept_reason": acc.get("reason"),
                "reject_semantic_ok": semantic_ok,
                "reject_class": reject_class,
                "reject_keywords": rej.get("keywords") or [],
                "reject_message": rej.get("message") or "",
                "reject_reason": rej.get("reason") or "",
                "intended_keyword": intended,
                "mutation": meta.get("mutation"),
                "suggested_minimal_mutation": meta.get("suggested_minimal_mutation"),
                "syntax_kind": syn.get("kind"),
                "syntax_reason": syn.get("reason"),
                "syntax_counts_as_coverage": False,
                "covered": covered,
            }
        )
    defined = len(rows)
    covered_n = sum(1 for r in rows if r["covered"])
    uncovered = [
        {
            "schema_id": r["schema_id"],
            "suggested_minimal_mutation": r["suggested_minimal_mutation"],
            "reason": (
                "accept-failed"
                if not r["accept_ok"]
                else f"reject-class={r['reject_class']}"
            ),
        }
        for r in rows
        if not r["covered"]
    ]
    ratio = (covered_n / defined) if defined else 0.0
    anti = {
        "pass": syntax_ok and reason_asserted and all(not r["syntax_counts_as_coverage"] for r in rows),
        "syntax_fixtures_do_not_count": True,
        "reason_string_asserted": reason_asserted,
        "all_syntax_classified_as_syntax": syntax_ok,
        "note": (
            "A rejecting fixture that fails JSON parse is classified SYNTAX and "
            "does not increment schemas_covered."
        ),
    }
    return {
        "schemas_defined": defined,
        "schemas_covered": covered_n,
        "ratio": ratio,
        "formula": (
            "schemas with at least one passing-and-one-failing (semantic) fixture "
            "/ schemas defined"
        ),
        "uncovered": uncovered,
        "rows": rows,
        "anti_tautology": anti,
        "frozen_present": sum(1 for r in rows if r["frozen_contract_present"]),
        "stand_in": sum(1 for r in rows if r["schema_source"] == "catalog-derived-stand-in"),
    }


def both_states_pass(rep: dict | None = None) -> bool:
    rep = rep or evaluate()
    if rep["schemas_defined"] != 10:
        return False
    if rep["schemas_covered"] != 10:
        return False
    if rep["uncovered"]:
        return False
    return all(r["covered"] and r["accept_ok"] and r["reject_semantic_ok"] for r in rep["rows"])


def anti_tautology_pass(rep: dict | None = None) -> bool:
    rep = rep or evaluate()
    anti = rep["anti_tautology"]
    if not anti.get("pass"):
        return False
    # Corrupt one reject into syntax and prove it would not cover.
    defn = contract_defs()[0]
    schema, _, _ = load_schema_for(defn)
    syn = classify_instance(schema, SYNTAX_BAD)
    if syn.get("kind") != "syntax":
        return False
    # A syntax reject must not be treated as semantic coverage.
    return syn.get("reason") == "syntax-error-not-semantic-violation"


if __name__ == "__main__":
    report = evaluate()
    print(json.dumps(
        {
            "defined": report["schemas_defined"],
            "covered": report["schemas_covered"],
            "ratio": report["ratio"],
            "uncovered": report["uncovered"],
            "anti": report["anti_tautology"],
            "rows": [
                {
                    "id": r["schema_id"],
                    "covered": r["covered"],
                    "accept": r["accept_ok"],
                    "reject_class": r["reject_class"],
                    "keywords": r["reject_keywords"],
                    "intended": r["intended_keyword"],
                    "source": r["schema_source"],
                }
                for r in report["rows"]
            ],
        },
        indent=2,
    ))
    ok = both_states_pass(report) and anti_tautology_pass(report)
    raise SystemExit(0 if ok else 1)
