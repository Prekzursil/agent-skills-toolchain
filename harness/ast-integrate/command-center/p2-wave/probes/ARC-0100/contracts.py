"""Per-contract unknown-field policy for ARC-0100.

Phase-4 contract files are the catalog inputs. If they are present and are
JSON Schemas they are used; otherwise the stand-in schemas below (derived from
the catalog question plus live A2/catalog shapes) are the executable contract.
A policy without a named producer/consumer pair is UNJUSTIFIED.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PHASE4 = REPO / "command-center" / "phase4" / "contracts"
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"

CONTRACT_IDS = (
    "ARC-0078",
    "ARC-0079",
    "ARC-0082",
    "ARC-0083",
    "ARC-0092",
)
FUTURE_FIELD = "future_optional_field"

SUBSTRATES = (
    "worktree-isolated",
    "local-parallel",
    "local-serialized",
    "cloud-batch",
    "local-windows-pwsh7",
)

FAIL_CLASSES = (
    "detector-failure",
    "mutation-survives",
    "schema-invalid",
    "overclaim",
    "spec-drift",
    "docs-code-divergence",
    "green-not-live",
    "uncontrolled-silence",
)

# Stand-in instance schemas. additionalProperties is left true: ARC-0100's
# validator flag owns the unknown-field axis.
STANDIN_SCHEMAS: dict[str, dict[str, Any]] = {
    "ARC-0078": {
        "$id": "arc-0100-standin://ARC-0078",
        "title": "Plugin manifest (ARC-0078 stand-in)",
        "type": "object",
        "additionalProperties": True,
        "required": [
            "name",
            "version",
            "description",
            "hooks",
            "compatibility",
        ],
        "properties": {
            "name": {"type": "string", "minLength": 1},
            "version": {"type": "string", "minLength": 1},
            "description": {"type": "string", "minLength": 1},
            "hooks": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "required": ["script", "interpreter", "event"],
                    "properties": {
                        "script": {"type": "string", "minLength": 1},
                        "interpreter": {"type": "string", "minLength": 1},
                        "event": {"type": "string", "minLength": 1},
                    },
                    "additionalProperties": True,
                },
            },
            "skills": {"type": "array", "items": {"type": "string"}},
            "rules": {"type": "array", "items": {"type": "string"}},
            "compatibility": {
                "type": "object",
                "required": ["min_client", "max_client"],
                "properties": {
                    "min_client": {"type": "string", "minLength": 1},
                    "max_client": {"type": "string", "minLength": 1},
                },
                "additionalProperties": True,
            },
        },
    },
    "ARC-0079": {
        "$id": "arc-0100-standin://ARC-0079",
        "title": "Marketplace registry entry (ARC-0079 stand-in)",
        "type": "object",
        "additionalProperties": True,
        "required": [
            "package_id",
            "namespace",
            "versions",
            "provenance",
            "license",
        ],
        "properties": {
            "package_id": {"type": "string", "minLength": 3},
            "namespace": {"type": "string", "minLength": 1},
            "versions": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "required": ["version", "channel", "state"],
                    "properties": {
                        "version": {"type": "string", "minLength": 1},
                        "channel": {"type": "string", "minLength": 1},
                        "state": {
                            "type": "string",
                            "enum": ["released", "deprecated", "revoked"],
                        },
                        "reason": {"type": "string"},
                    },
                    "additionalProperties": True,
                },
            },
            "provenance": {
                "type": "object",
                "required": ["source", "digest"],
                "properties": {
                    "source": {"type": "string", "minLength": 1},
                    "digest": {"type": "string", "minLength": 8},
                },
                "additionalProperties": True,
            },
            "license": {"type": "string", "minLength": 1},
            "sbom_ref": {"type": "string"},
            "signature_ref": {"type": "string"},
            "quality_score": {"type": "number"},
        },
    },
    "ARC-0082": {
        "$id": "arc-0100-standin://ARC-0082",
        "title": "Workflow DSL (ARC-0082 stand-in)",
        "type": "object",
        "additionalProperties": True,
        "required": ["id", "stages", "failure_policy"],
        "properties": {
            "id": {"type": "string", "minLength": 3},
            "stages": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "required": ["id", "kind"],
                    "properties": {
                        "id": {"type": "string", "minLength": 1},
                        "kind": {"type": "string", "minLength": 1},
                        "inputs": {"type": "array", "items": {"type": "string"}},
                        "outputs": {"type": "array", "items": {"type": "string"}},
                    },
                    "additionalProperties": True,
                },
            },
            "gates": {"type": "array"},
            "failure_policy": {"type": "string", "minLength": 3},
            "replayable": {"type": "boolean"},
            "certified_executable": {"type": "boolean"},
            "discovery_only": {"type": "boolean"},
        },
    },
    "ARC-0083": {
        "$id": "arc-0100-standin://ARC-0083",
        "title": "Work-unit schema (ARC-0083 stand-in)",
        "type": "object",
        "additionalProperties": True,
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
            "id": {"type": "string", "minLength": 6},
            "title": {"type": "string", "minLength": 8},
            "phase": {"type": ["string", "integer"]},
            "target": {"type": "string", "minLength": 8},
            "inputs": {"type": "array"},
            "dependencies": {"type": "array"},
            "assignment": {"type": "object"},
            "tool_permissions": {"type": "array", "items": {"type": "string"}},
            "execution_substrate": {"type": "string", "enum": list(SUBSTRATES)},
            "timeout_seconds": {"type": "integer", "minimum": 1},
            "output_path": {"type": "string", "minLength": 8},
            "output_schema": {"type": "string", "minLength": 8},
            "evidence_requirement": {"type": "string", "minLength": 8},
            "tests_required": {"type": "array"},
            "reviewer_requirement": {"type": "string", "minLength": 8},
            "completion_sentinel": {"type": "string", "minLength": 8},
            "retry_policy": {"type": "string", "minLength": 8},
            "failure_classification": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "string", "enum": list(FAIL_CLASSES)},
            },
            "owner_approval_required": {"type": "boolean"},
        },
    },
    "ARC-0092": {
        "$id": "arc-0100-standin://ARC-0092",
        "title": "Versioning rules (ARC-0092 stand-in)",
        "type": "object",
        "additionalProperties": True,
        "required": [
            "artifact_class",
            "breaking_changes",
            "additive_changes",
            "deprecation_window_releases",
        ],
        "properties": {
            "artifact_class": {"type": "string", "minLength": 3},
            "breaking_changes": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "string", "minLength": 3},
            },
            "additive_changes": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "string", "minLength": 3},
            },
            "deprecation_window_releases": {"type": "integer", "minimum": 0},
            "deprecation_window_days": {"type": "integer", "minimum": 0},
        },
    },
}

GOLDEN: dict[str, dict[str, Any]] = {
    "ARC-0078": {
        "name": "harness",
        "version": "1.0.0",
        "description": "A2 generated plugin manifest for the harness control plane.",
        "hooks": "./hooks.json",
        "skills": ["skills/skill.council/SKILL.md"],
        "engines": {
            "host": {
                "min": "1.0.0",
                "clients": ["claude-code", "codex", "cursor"],
            }
        },
    },
    "ARC-0079": {
        "package_id": "harness.control-plane",
        "namespace": "harness",
        "versions": [
            {"version": "1.0.0", "channel": "stable", "state": "released"},
            {
                "version": "0.9.0",
                "channel": "stable",
                "state": "revoked",
                "reason": "CVE-placeholder-revocation-must-be-expressible",
            },
        ],
        "provenance": {
            "source": "a2-registry",
            "digest": "sha256:deadbeef",
        },
        "license": "Apache-2.0",
    },
    "ARC-0082": {
        "id": "wf.catalog-class.discovery-only",
        "stages": [
            {"id": "discover", "kind": "static-scan", "role": "scanner"},
            {"id": "record", "kind": "write-config", "role": "writer"},
        ],
        "entry": "discover",
        "failure_policy": "halt",
        "replayable": False,
        "certified_executable": False,
        "prompt_transport": "file",
    },
    "ARC-0083": {
        "id": "ARC-0100",
        "title": "Unknown-field policy: strict rejection versus tolerant ignore",
        "phase": "4",
        "target": "Decide REJECT vs IGNORE per contract with producer/consumer named.",
        "inputs": ["command-center/phase4/contracts/ARC-0078.json"],
        "dependencies": ["ARC-0078", "ARC-0079", "ARC-0082", "ARC-0083", "ARC-0092"],
        "assignment": {"model": "opus", "role": "test-engineer", "vendor": "anthropic"},
        "tool_permissions": ["Read", "Grep", "Glob", "Bash", "Write", "Edit"],
        "execution_substrate": "worktree-isolated",
        "timeout_seconds": 3600,
        "output_path": "command-center/phase4/conformance/ARC-0100.json",
        "output_schema": "command-center/schema/conformance-report.schema.json",
        "evidence_requirement": "Name the producer/consumer pair and who moves first.",
        "tests_required": ["forward-compat", "both-states"],
        "reviewer_requirement": "Independent reviewer re-runs the suite.",
        "completion_sentinel": "SUCCESS:ARC-0100",
        "retry_policy": "retry once after fixing validator input",
        "failure_classification": [
            "detector-failure",
            "mutation-survives",
            "schema-invalid",
            "overclaim",
        ],
        "owner_approval_required": False,
    },
    "ARC-0092": {
        "contract_id": "ARC-0092",
        "artifact_class": "schema",
        "from_ref": "command-center/p2-wave/probes/ARC-0010/registry.schema.json",
        "to_ref": "command-center/p2-wave/probes/ARC-0010/registry.schema.json",
        "required_bump": "NONE",
        "changes": [],
        "computed_not_asserted": True,
    },
}

# Seeded failure class: strict client parser rejects an unknown field a newer
# producer emitted (spec 11302 / FC-11302).
POLICIES: dict[str, dict[str, str]] = {
    "ARC-0078": {
        "policy": "REJECT",
        "producer": "plugin author / A2 generator (emits plugin.json)",
        "consumer": "host plugin parser (Claude warns; Codex HooksFile/manifest serde deny_unknown_fields)",
        "who_moves_first": "producer",
        "justification": "JUSTIFIED",
        "consequence_if_reject_wrong": (
            "A newer producer cannot add a frozen-key field without a client bump; "
            "additive work must wait for the consumer or a later reserved-prefix unit."
        ),
        "consequence_if_ignore_wrong": (
            "Producer ships a new field; a strict client rejects the whole manifest; "
            "the plugin is reported installed while loading ZERO hooks (FC-11303 neighbor)."
        ),
        "why": (
            "Consumer is already deployed and, on the strictest supported client, rejects "
            "unknown top-level keys. Producer must move first inside the frozen key set. "
            "Producer-side REJECT is the lint that keeps that client from seeing extras."
        ),
    },
    "ARC-0079": {
        "policy": "IGNORE",
        "producer": "marketplace index publisher",
        "consumer": "installer / already-installed client reading the registry",
        "who_moves_first": "producer",
        "justification": "JUSTIFIED",
        "consequence_if_reject_wrong": (
            "An old strict installer rejects a newer index entry and never learns a "
            "revocation that was added as metadata beside frozen version-state fields."
        ),
        "consequence_if_ignore_wrong": (
            "Security-critical meaning placed only in a new field is skipped by old "
            "clients; revocation and provenance must stay on frozen keys."
        ),
        "why": (
            "Producer evolves the index faster than installed clients. ARC-0079 requires "
            "an already-installed client to learn about revoked versions. Consumer IGNORE "
            "on unknown keys keeps frozen revocation/state readable while new optional "
            "metadata (SBOM, quality score) is skipped."
        ),
    },
    "ARC-0082": {
        "policy": "REJECT",
        "producer": "workflow / blueprint author",
        "consumer": "workflow engine that interprets stages, gates, and failure policy",
        "who_moves_first": "consumer",
        "justification": "JUSTIFIED",
        "consequence_if_reject_wrong": (
            "An old engine cannot run a blueprint that uses a new construct until the "
            "engine is bumped — fail closed, which is the safety default."
        ),
        "consequence_if_ignore_wrong": (
            "An unknown stage or gate kind is skipped. A new approval-gate would fail "
            "open: the workflow runs without the control the author wrote."
        ),
        "why": (
            "Unknown executable constructs must not be skipped. Consumer (engine) moves "
            "first: a new construct is illegal until the engine names it."
        ),
    },
    "ARC-0083": {
        "policy": "REJECT",
        "producer": "work-unit / catalog author",
        "consumer": "completeness validator and CI unitgate",
        "who_moves_first": "consumer",
        "justification": "JUSTIFIED",
        "consequence_if_reject_wrong": (
            "Adding a catalog field requires a schema bump first. Authors wait for the "
            "validator (the defect this contract exists to close: defaults are not completeness)."
        ),
        "consequence_if_ignore_wrong": (
            "A typo for a mandatory field (target vs question_or_target, assignment vs "
            "assigned_model_vendor_role) is dropped; completeness still passes via defaults."
        ),
        "why": (
            "The measured hole is mandatory fields supplied only as catalogue-level defaults. "
            "IGNORE would hide a misspelled per-unit field. Consumer (validator) moves first."
        ),
    },
    "ARC-0092": {
        "policy": "REJECT",
        "producer": "schema-diff / release declaration author",
        "consumer": "version-bump calculator",
        "who_moves_first": "consumer",
        "justification": "JUSTIFIED",
        "consequence_if_reject_wrong": (
            "A new breaking-change axis cannot be declared until the calculator names it."
        ),
        "consequence_if_ignore_wrong": (
            "A new breaking classification is dropped; a breaking change is under-bumped "
            "as additive."
        ),
        "why": (
            "The calculator's job is classifying breaking vs additive. Unknown axes must "
            "not vanish. Consumer moves first."
        ),
    },
}


def _looks_like_schema(doc: Any) -> bool:
    if not isinstance(doc, dict):
        return False
    if doc.get("type") == "object" and isinstance(doc.get("properties"), dict):
        return True
    inner = doc.get("schema") or doc.get("instance_schema") or doc.get("json_schema")
    return isinstance(inner, dict) and isinstance(inner.get("properties"), dict)


def _extract_schema(doc: dict) -> dict:
    if doc.get("type") == "object" and isinstance(doc.get("properties"), dict):
        return doc
    for key in ("schema", "instance_schema", "json_schema"):
        inner = doc.get(key)
        if isinstance(inner, dict) and isinstance(inner.get("properties"), dict):
            return inner
    raise ValueError("not a schema")


def load_schema(uid: str) -> tuple[dict, str, str]:
    """Return (schema, source, phase4_path). source is phase4-file or stand-in."""
    path = PHASE4 / f"{uid}.json"
    rel = path.relative_to(REPO).as_posix()
    if path.is_file() and path.stat().st_size > 0:
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
            if _looks_like_schema(doc):
                return _extract_schema(doc), "phase4-file", rel
            return STANDIN_SCHEMAS[uid], "stand-in-phase4-not-schema", rel
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
            return STANDIN_SCHEMAS[uid], "stand-in-phase4-unparseable", rel
    return STANDIN_SCHEMAS[uid], "stand-in-phase4-absent", rel


def with_future_field(instance: dict) -> dict:
    out = dict(instance)
    out[FUTURE_FIELD] = "v2-producer-emitted"
    return out


def catalog_unit(uid: str) -> dict | None:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    for u in data.get("work_units") or []:
        if isinstance(u, dict) and u.get("id") == uid:
            return u
    return None
