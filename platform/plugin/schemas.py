"""JSON Schemas for every artifact this package emits, plus the shipped plugin manifest schema.

These are not decoration. Each schema is the contract for an artifact that a function in this
package actually produces, and ``test_schemas.py`` validates the REAL emitted object against it
(plus a negative control that must fail). A schema nothing produces is untested documentation.

The definitions live here as Python dicts so there is exactly one source of truth, and
``materialise()`` writes them to the paths the work-unit catalog declares:

* ``tools/plugin/schema/<name>.schema.json`` — 18 artifact schemas;
* ``.claude-plugin/plugin.schema.json`` — the manifest schema, which extends (never contradicts)
  the repo-root ``.claude-plugin/plugin.json`` that Claude Code already reads.

``check()`` compares disk against this module, so a hand-edit of a generated file is a test
failure rather than silent drift.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .errors import TAXONOMY
from .manifest import DEPLOY_MODES, ENTRYPOINT_KINDS, SEMVER_RE
from .proc import INTERPRETERS

DRAFT = "https://json-schema.org/draft/2020-12/schema"
BASE_URI = "https://prekzursil.dev/ast-integrate/schema"

_HASH = {"type": "string", "pattern": "^[0-9a-f]{64}$"}
_HASH_OR_NULL = {"type": ["string", "null"], "pattern": "^[0-9a-f]{64}$"}


def _obj(
    title: str,
    artifact: str,
    props: dict[str, Any],
    required: list[str],
    *,
    additional: bool = False,
    description: str = "",
) -> dict[str, Any]:
    schema: dict[str, Any] = {
        "$schema": DRAFT,
        "$id": f"{BASE_URI}/{artifact}.schema.json",
        "title": title,
        "type": "object",
        "properties": {"artifact": {"const": artifact}, **props},
        "required": ["artifact", *required],
        "additionalProperties": additional,
    }
    if description:
        schema["description"] = description
    return schema


_COUNT = {"type": "integer", "minimum": 0}
_PATH = {"type": "string", "minLength": 1}

DRIFT_CLASSES = [
    "unchanged",
    "upstream_only",
    "live_only",
    "diverged",
    "live_absent",
    "untracked_live",
]

SCHEMAS: dict[str, dict[str, Any]] = {}

SCHEMAS["payload-allowlist"] = _obj(
    "Package payload allowlist (deny-by-default include set)",
    "payload-allowlist",
    {
        "policy": {"const": "deny-by-default"},
        "rules": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "properties": {
                    "glob": _PATH,
                    "reason": {"type": "string", "minLength": 1},
                },
                "required": ["glob", "reason"],
                "additionalProperties": False,
            },
        },
        "budget": {
            "type": "object",
            "properties": {"max_bytes": _COUNT, "max_files": _COUNT},
            "required": ["max_bytes", "max_files"],
            "additionalProperties": False,
        },
        "forbidden_classes": {
            "type": "object",
            "minProperties": 1,
            "additionalProperties": {"type": "array", "items": {"type": "string"}},
        },
    },
    ["policy", "rules", "budget", "forbidden_classes"],
    description="An exclude-only policy is unsound: the first unlisted junk directory ships. "
    "`policy` is pinned to deny-by-default so a widened build cannot claim conformance.",
)

SCHEMAS["payload-inventory"] = _obj(
    "Staged payload inventory with per-file EOL-normalised hashes",
    "payload-inventory",
    {
        "plugin": {"type": "string"},
        "version": {"type": "string", "pattern": SEMVER_RE.pattern},
        "total_bytes": _COUNT,
        "file_count": _COUNT,
        "entries": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "path": _PATH,
                    "size": _COUNT,
                    "sha256": _HASH,
                    "rule": {"type": "string"},
                },
                "required": ["path", "size", "sha256", "rule"],
                "additionalProperties": False,
            },
        },
        "forbidden_classes_checked": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
        },
        "forbidden_matches": {"type": "array", "maxItems": 0},
    },
    [
        "plugin",
        "version",
        "total_bytes",
        "file_count",
        "entries",
        "forbidden_classes_checked",
        "forbidden_matches",
    ],
    description="`forbidden_matches` has maxItems 0: an inventory that records a forbidden match "
    "is invalid by construction, so the value cannot be reported as a warning.",
)

SCHEMAS["secret-finding"] = _obj(
    "Credential-exposure finding (shape only, never the value)",
    "secret-finding",
    {
        "scanned_files": _COUNT,
        "blocking": _COUNT,
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "path": _PATH,
                    "rule": {"type": "string", "minLength": 1},
                    "line": {"type": "integer", "minimum": 1},
                    "severity": {"enum": ["blocking", "advisory"]},
                    "excerpt_shape": {
                        "type": "string",
                        "pattern": r"^len=\d+ entropy=\d+\.\d+bits$",
                    },
                },
                "required": ["path", "rule", "line", "severity", "excerpt_shape"],
                "additionalProperties": False,
            },
        },
    },
    ["scanned_files", "blocking", "findings"],
    description="`excerpt_shape` is pattern-pinned to a length+entropy descriptor, so a finding "
    "physically cannot carry the matched secret.",
)

SCHEMAS["compatibility"] = _obj(
    "Client / OS / shell compatibility diagnostics",
    "compatibility",
    {
        "os": {"enum": ["windows", "macos", "linux"]},
        "shell": {"type": "object"},
        "interpreters": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "interpreter": {"enum": sorted(INTERPRETERS)},
                    "found": {"type": "boolean"},
                    "path": {"type": ["string", "null"]},
                    "version": {"type": ["string", "null"]},
                    "floor": {"type": ["string", "null"]},
                    "meets_floor": {"type": "boolean"},
                    "detail": {"type": "string"},
                },
                "required": ["interpreter", "found", "meets_floor", "detail"],
                "additionalProperties": False,
            },
        },
        "client": {"type": ["object", "null"]},
        "compatible": {"type": ["boolean", "null"]},
        "reasons": {"type": "array", "items": {"type": "string"}},
        "required_interpreters": {"type": "array", "items": {"type": "string"}},
        "plugin": {"type": "object"},
    },
    ["os", "shell", "interpreters", "compatible", "reasons"],
)

SCHEMAS["projection-map"] = _obj(
    "Manifest-to-live-config projection map",
    "projection-map",
    {
        "plugin": {"type": "string"},
        "version": {"type": "string"},
        "targets": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "source": {"type": "string"},
                    "target": {"type": "string"},
                    "mode": {"enum": sorted(DEPLOY_MODES)},
                    "file_count": _COUNT,
                },
                "required": ["source", "target", "mode", "file_count"],
                "additionalProperties": False,
            },
        },
        "entrypoints": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "kind": {"enum": sorted(ENTRYPOINT_KINDS)},
                    "path": {"type": "string"},
                    "interpreter": {"type": ["string", "null"]},
                    "launch": {
                        "type": "object",
                        "additionalProperties": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                },
                "required": ["id", "kind", "path", "launch"],
                "additionalProperties": False,
            },
        },
    },
    ["plugin", "version", "targets", "entrypoints"],
    description="Records the per-OS argv array each entrypoint resolves to, so the projection is "
    "auditable without running the plugin.",
)

SCHEMAS["txn-journal"] = _obj(
    "Lifecycle transaction journal",
    "txn-journal",
    {
        "prefix": _PATH,
        "record_count": _COUNT,
        "open_transactions": {"type": "array", "items": {"type": "string"}},
        "records": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "ts": {"type": "number"},
                    "event": {
                        "enum": [
                            "open",
                            "step",
                            "commit",
                            "abort",
                            "recovered",
                            "unparseable",
                        ]
                    },
                    "op": {"type": "string"},
                    "txn": {"type": "string"},
                },
                "required": ["ts", "event"],
                "additionalProperties": True,
            },
        },
    },
    ["prefix", "record_count", "open_transactions", "records"],
)

SCHEMAS["deploy-provenance"] = _obj(
    "Per-file deploy provenance",
    "deploy-provenance",
    {
        "record_count": _COUNT,
        "records": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "live_path": _PATH,
                    "source_path": _PATH,
                    "version": {"type": "string"},
                    "content_sha256": _HASH,
                    "deployed_at": {"type": "number"},
                    "mode": {"enum": sorted(DEPLOY_MODES)},
                },
                "required": [
                    "live_path",
                    "source_path",
                    "version",
                    "content_sha256",
                    "deployed_at",
                    "mode",
                ],
                "additionalProperties": False,
            },
        },
    },
    ["record_count", "records"],
    description="The provenance hash is the third reading the drift classifier needs; without it "
    "only a one-directional comparison is possible and DIVERGED is invisible.",
)

SCHEMAS["drift-classification"] = _obj(
    "Two-directional live-versus-source drift classification",
    "drift-classification",
    {
        "bidirectional": {"const": True},
        "hash_algorithm": {"const": "sha256-over-LF-normalised-bytes"},
        "counts": {
            "type": "object",
            "properties": {k: _COUNT for k in DRIFT_CLASSES},
            "required": DRIFT_CLASSES,
            "additionalProperties": False,
        },
        "entries": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "live_path": _PATH,
                    "source_path": {"type": ["string", "null"]},
                    "classification": {"enum": DRIFT_CLASSES},
                    "live_sha256": _HASH_OR_NULL,
                    "source_sha256": _HASH_OR_NULL,
                    "provenance_sha256": _HASH_OR_NULL,
                    "reason": {"type": "string", "minLength": 1},
                },
                "required": ["live_path", "classification", "reason"],
                "additionalProperties": False,
            },
        },
    },
    ["bidirectional", "hash_algorithm", "counts", "entries"],
    description="`bidirectional` is a const and `counts` must enumerate all six classes, so a "
    "one-directional classifier (which cannot see DIVERGED) cannot emit a valid document.",
)

SCHEMAS["divergence-decision"] = _obj(
    "Diverged-file decision packet (never auto-resolved)",
    "divergence-decision",
    {
        "auto_resolved": {"const": False},
        "decision_required": _COUNT,
        "decisions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "live_path": _PATH,
                    "source_path": {"type": ["string", "null"]},
                    "live_sha256": _HASH_OR_NULL,
                    "source_sha256": _HASH_OR_NULL,
                    "provenance_sha256": _HASH_OR_NULL,
                    "reason": {"type": "string"},
                    "options": {
                        "type": "array",
                        "items": {
                            "enum": ["keep_live", "take_source", "merge_manually"]
                        },
                        "minItems": 3,
                    },
                    "chosen": {"type": "null"},
                },
                "required": ["live_path", "reason", "options", "chosen"],
                "additionalProperties": False,
            },
        },
    },
    ["auto_resolved", "decision_required", "decisions"],
    description="`chosen` is pinned to null: a packet emitted by the tool can never be mistaken "
    "for a resolution, so the owner decision cannot be forged by the tool that found the conflict.",
)

SCHEMAS["health-report"] = _obj(
    "Health-check report",
    "health-report",
    {
        "os": {"enum": ["windows", "macos", "linux"]},
        "probe_count": {"type": "integer", "minimum": 1},
        "passed": _COUNT,
        "failed": _COUNT,
        "skipped": _COUNT,
        "ok": {"type": "boolean"},
        "probes": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "properties": {
                    "probe": {"type": "string", "minLength": 1},
                    "status": {"enum": ["PASS", "FAIL", "SKIP"]},
                    "detail": {"type": "string", "minLength": 1},
                    "remediation": {"type": "string"},
                },
                "required": ["probe", "status", "detail", "remediation"],
                "additionalProperties": False,
            },
        },
        "controls": {"type": "array"},
    },
    ["os", "probe_count", "passed", "failed", "skipped", "ok", "probes"],
    description="`probe_count` has a minimum of 1: a report from an empty probe registry is not a "
    "green health check, it is a broken harness.",
)

SCHEMAS["probe-control"] = _obj(
    "Both-states control results for every health probe",
    "probe-control",
    {
        "probe_count": {"type": "integer", "minimum": 1},
        "valid": _COUNT,
        "invalid": _COUNT,
        "not_checked": _COUNT,
        "rows": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "properties": {
                    "probe": {"type": "string"},
                    "healthy_status": {"enum": ["PASS", "FAIL", "SKIP"]},
                    "broken_status": {"enum": ["PASS", "FAIL", "SKIP", None]},
                    "restored_status": {"enum": ["PASS", "FAIL", "SKIP"]},
                    "discriminates": {"type": ["boolean", "null"]},
                    "verdict": {"enum": ["VALID", "INVALID", "SKIP", "NOT-CHECKED"]},
                    "reason": {"type": "string"},
                },
                "required": ["probe", "healthy_status", "verdict"],
                "additionalProperties": False,
            },
        },
    },
    ["probe_count", "valid", "invalid", "not_checked", "rows"],
    description="A probe with no declared break_() is recorded NOT-CHECKED, never folded into the "
    "valid count.",
)

SCHEMAS["conformance-report"] = _obj(
    "Plugin conformance report (positive assertion, N of N)",
    "conformance-report",
    {
        "package": _PATH,
        "condition_count": {"type": "integer", "minimum": 1},
        "satisfied": _COUNT,
        "violated": _COUNT,
        "not_checked": _COUNT,
        "ok": {"type": "boolean"},
        "verdict": {"type": "string", "pattern": r"^\d+/\d+ conditions satisfied$"},
        "conditions": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "pattern": "^C[0-9]{2}$"},
                    "requirement": {"type": "string", "minLength": 1},
                    "status": {"enum": ["SATISFIED", "VIOLATED", "NOT-CHECKED"]},
                    "evidence": {"type": "string", "minLength": 1},
                },
                "required": ["id", "requirement", "status", "evidence"],
                "additionalProperties": False,
            },
        },
    },
    [
        "package",
        "condition_count",
        "satisfied",
        "violated",
        "not_checked",
        "ok",
        "verdict",
        "conditions",
    ],
    description="`verdict` must spell out N/N. 'nothing blocking' is not expressible in this schema.",
)

SCHEMAS["migration-step"] = _obj(
    "Planned migration steps for a detected legacy layout",
    "migration-step",
    {
        "detected_layout": {"type": "string", "minLength": 1},
        "step_count": _COUNT,
        "steps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "description": {"type": "string", "minLength": 1},
                    "inverse": {"type": "string", "minLength": 1},
                },
                "required": ["id", "description", "inverse"],
                "additionalProperties": False,
            },
        },
    },
    ["detected_layout", "step_count", "steps"],
    description="Every step carries a non-empty `inverse`; a step with no inverse cannot be planned.",
)

SCHEMAS["migration-ledger"] = _obj(
    "Migration provenance ledger",
    "migration-ledger",
    {
        "root": _PATH,
        "detected_layout": {"type": "string"},
        "dry_run": {"type": "boolean"},
        "started_at": {"type": "number"},
        "finished_at": {"type": "number"},
        "applied": {"type": "array"},
        "rolled_back": {"type": "array", "items": {"type": "string"}},
        "undo_failures": {"type": "array", "items": {"type": "string"}},
        "ok": {"type": "boolean"},
        "error": {"type": "string"},
        "note": {"type": "string"},
        "would_apply": {"type": "array"},
    },
    [
        "root",
        "detected_layout",
        "dry_run",
        "started_at",
        "applied",
        "rolled_back",
        "ok",
    ],
)

SCHEMAS["error-taxonomy"] = _obj(
    "Stable, documented error-code taxonomy",
    "error-taxonomy",
    {
        "version": {"type": "integer", "minimum": 1},
        "classes": {
            "type": "array",
            "minItems": len(TAXONOMY),
            "items": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "pattern": "^E_[A-Z_]+$"},
                    "exit_code": {"type": "integer", "minimum": 0, "maximum": 125},
                    "title": {"type": "string", "minLength": 1},
                    "cause": {"type": "string", "minLength": 1},
                    "impact": {"type": "string", "minLength": 1},
                    "next_command": {"type": "string", "minLength": 1},
                    "fail_mode": {"enum": ["fail-open", "fail-closed"]},
                },
                "required": [
                    "code",
                    "exit_code",
                    "title",
                    "cause",
                    "impact",
                    "next_command",
                    "fail_mode",
                ],
                "additionalProperties": False,
            },
        },
    },
    ["version", "classes"],
    description="minItems is pinned to the current class count, so removing a published error "
    "class is a schema violation rather than a silent contract break. `next_command` is required: "
    "a message with no next step is not a user-facing error.",
)

SCHEMAS["failure-policy"] = _obj(
    "Per-component fail-open versus fail-closed policy",
    "failure-policy",
    {
        "default_mode": {"const": "fail-closed"},
        "fail_open_count": _COUNT,
        "rules": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "properties": {
                    "component": {"type": "string", "minLength": 1},
                    "mode": {"enum": ["fail-open", "fail-closed"]},
                    "error_code": {"type": "string", "pattern": "^E_[A-Z_]+$"},
                    "reason": {"type": "string", "minLength": 1},
                },
                "required": ["component", "mode", "error_code", "reason"],
                "additionalProperties": False,
            },
        },
    },
    ["default_mode", "fail_open_count", "rules"],
    description="Every fail-open row must carry a reason; the default is pinned to fail-closed.",
)

SCHEMAS["exec-policy"] = _obj(
    "Execution policy for plugin-shipped scripts",
    "exec-policy",
    {
        "default_trigger": {"const": "explicit-invocation-only"},
        "install_runs_shipped_code": {"const": False},
        "credential_boundary": {"type": "string", "minLength": 1},
        "rules": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "properties": {
                    "entrypoint_kind": {"enum": sorted(ENTRYPOINT_KINDS)},
                    "trigger": {
                        "enum": ["explicit-invocation-only", "on-install", "automatic"]
                    },
                    "interpreter_required": {"type": "boolean"},
                    "network_allowed": {"type": "boolean"},
                    "credential_read_allowed": {"const": False},
                    "rationale": {"type": "string", "minLength": 1},
                },
                "required": [
                    "entrypoint_kind",
                    "trigger",
                    "interpreter_required",
                    "network_allowed",
                    "credential_read_allowed",
                    "rationale",
                ],
                "additionalProperties": False,
            },
        },
    },
    ["default_trigger", "install_runs_shipped_code", "credential_boundary", "rules"],
    description="`credential_read_allowed` is a const false and `install_runs_shipped_code` a "
    "const false: neither can be widened by editing the policy document.",
)

SCHEMAS["log-record"] = _obj(
    "Structured log record with mandatory redaction",
    "log-record",
    {
        "ts": {"type": "number"},
        "level": {"enum": ["debug", "info", "warn", "error"]},
        "op": {"type": "string", "minLength": 1},
        "event": {"type": "string", "minLength": 1},
        "fields": {"type": "object"},
    },
    ["ts", "level", "op", "event", "fields"],
    additional=False,
    description="Records are emitted one per line as JSONL; this schema validates one line.",
)
# a log record is not an `artifact`-tagged envelope, so drop the artifact pin
SCHEMAS["log-record"]["properties"].pop("artifact")
SCHEMAS["log-record"]["required"] = ["ts", "level", "op", "event", "fields"]

#: The shipped manifest schema. Deliberately mirrors ``manifest.py``'s strict parser: the parser is
#: normative (it produces the specific ``E_MANIFEST`` message), and this schema is the machine
#: readable form a third party can validate against without running our code.
PLUGIN_MANIFEST_SCHEMA: dict[str, Any] = {
    "$schema": DRAFT,
    "$id": f"{BASE_URI}/plugin.schema.json",
    "title": "Claude Code plugin manifest (.claude-plugin/plugin.json), strict profile",
    "description": (
        "A superset of the fields Claude Code reads: name/version/description/author/license/"
        "keywords/homepage keep their client meaning, and this profile adds compatibility, "
        "interpreters, entrypoints, payload budgets and deploy targets. Unknown properties are "
        "REJECTED except under the reserved 'x-' extension namespace, so a typo is an error "
        "rather than a silently dropped field."
    ),
    "type": "object",
    "properties": {
        "name": {"type": "string", "pattern": "^[a-z0-9][a-z0-9-]{1,63}$"},
        "version": {"type": "string", "pattern": SEMVER_RE.pattern},
        "description": {"type": "string", "minLength": 1},
        "author": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "minLength": 1},
                "email": {"type": "string"},
                "url": {"type": "string"},
            },
            "required": ["name"],
            "additionalProperties": False,
        },
        "license": {"type": "string", "minLength": 1},
        "keywords": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
            "minItems": 1,
        },
        "homepage": {"type": "string"},
        "compatibility": {
            "type": "object",
            "properties": {
                "min_client": {"type": "string", "pattern": SEMVER_RE.pattern},
                "max_client": {"type": "string", "pattern": SEMVER_RE.pattern},
                "platforms": {
                    "type": "array",
                    "items": {"enum": ["windows", "macos", "linux"]},
                    "minItems": 1,
                    "uniqueItems": True,
                },
                "shells": {"type": "array", "items": {"type": "string"}},
                "schema_version": {"type": "integer", "minimum": 1},
            },
            "required": ["min_client"],
            "additionalProperties": False,
        },
        "interpreters": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"enum": sorted(INTERPRETERS)},
                    "floor": {"type": "string"},
                    "required": {"type": "boolean"},
                },
                "required": ["id"],
                "additionalProperties": False,
            },
        },
        "entrypoints": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "minLength": 1},
                    "kind": {"enum": sorted(ENTRYPOINT_KINDS)},
                    "path": {"type": "string", "minLength": 1},
                    "interpreter": {"enum": sorted(INTERPRETERS)},
                    "args": {"type": "array", "items": {"type": "string"}},
                    "description": {"type": "string"},
                },
                "required": ["id", "kind", "path"],
                "additionalProperties": False,
                "allOf": [
                    {
                        "if": {
                            "properties": {
                                "kind": {"enum": ["command", "hook", "script"]}
                            }
                        },
                        "then": {"required": ["interpreter"]},
                    }
                ],
            },
        },
        "payload": {
            "type": "object",
            "properties": {
                "max_bytes": {"type": "integer", "minimum": 1},
                "max_files": {"type": "integer", "minimum": 1},
                "include": {"type": "array", "items": {"type": "string"}},
                "exclude": {"type": "array", "items": {"type": "string"}},
            },
            "additionalProperties": False,
        },
        "deploy": {
            "type": "object",
            "properties": {
                "targets": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "source": {"type": "string"},
                            "target": {"type": "string"},
                            "mode": {"enum": sorted(DEPLOY_MODES)},
                        },
                        "required": ["source", "target", "mode"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["targets"],
            "additionalProperties": False,
        },
    },
    # IMP-0006: required set is the CURRENT Claude Code client surface so the live
    # `.claude-plugin/plugin.json` validates green. Phase-4 fields
    # (compatibility/interpreters/entrypoints/payload/deploy/homepage) remain
    # contracted properties above — optional until a package build supplies them.
    "required": [
        "name",
        "version",
        "description",
        "author",
        "license",
        "keywords",
    ],
    "additionalProperties": False,
    "patternProperties": {"^x-": {}},
}

#: Declared path -> schema document. Exactly the paths the work-unit catalog references.
TARGETS: dict[str, dict[str, Any]] = {
    **{f"tools/plugin/schema/{name}.schema.json": doc for name, doc in SCHEMAS.items()},
    ".claude-plugin/plugin.schema.json": PLUGIN_MANIFEST_SCHEMA,
}


def render(doc: dict[str, Any]) -> str:
    return json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def materialise(repo_root: Path) -> list[str]:
    """Write every schema to its declared path. Returns the paths written."""
    from .fsops import atomic_write_bytes

    written: list[str] = []
    for rel, doc in sorted(TARGETS.items()):
        target = repo_root / rel
        atomic_write_bytes(target, render(doc).encode("utf-8"))
        written.append(rel)
    return written


def check(repo_root: Path) -> list[str]:
    """Every declared path that is missing or differs from this module. Empty list = in sync."""
    problems: list[str] = []
    for rel, doc in sorted(TARGETS.items()):
        target = repo_root / rel
        if not target.exists():
            problems.append(f"{rel}: missing")
            continue
        on_disk = target.read_text(encoding="utf-8").replace("\r\n", "\n")
        if on_disk != render(doc):
            problems.append(f"{rel}: differs from platform/plugin/schemas.py")
    return problems
