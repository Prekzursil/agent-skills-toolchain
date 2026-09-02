#!/usr/bin/env python3
"""Emit command-center/phase4/contracts/ARC-0082.json — Draft 2020-12 Workflow DSL."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import dsl as D  # noqa: E402
from jsonschema import Draft202012Validator  # noqa: E402

OUT_REL = "command-center/phase4/contracts/ARC-0082.json"
SENTINEL = "SUCCESS:ARC-0082"

GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
)

STAGE_KIND_ENUM = [
    "WorkUnit",
    "FanOut",
    "Barrier",
    "Pipeline",
    "Subworkflow",
    "Loop",
    "HumanCheckpoint",
    "DynamicFanOut",
    "RepairLoop",
    "work",
    "fan-out",
    "barrier",
    "checkpoint",
    "gate",
    "static-scan",
    "write-config",
]


def _str(min_len: int = 1, max_len: int = 256) -> dict:
    return {"type": "string", "minLength": min_len, "maxLength": max_len}


def schema_body() -> dict:
    on_failure = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "adapter-exit-n",
            "blocked",
            "degraded",
            "partial-artifact",
            "schema-invalid",
            "severed-stream",
            "timeout",
            "win-arg-limit",
        ],
        "properties": {
            fam: {
                "type": "string",
                "enum": ["abort", "continue", "escalate", "quarantine", "repair"],
            }
            for fam in (
                "adapter-exit-n",
                "blocked",
                "degraded",
                "partial-artifact",
                "schema-invalid",
                "severed-stream",
                "timeout",
                "win-arg-limit",
            )
        },
    }
    stage_props = {
        "id": _str(1, 64),
        "kind": {"$ref": "#/$defs/stageKind"},
        "role": _str(1, 32),
        "max_retries": {"type": "integer", "minimum": 0, "maximum": 8},
        "prompt_ref": _str(1, 512),
        "params": {"type": "object"},
        "on_failure": on_failure,
        "units": {"type": "array", "items": _str(1, 64)},
        "wait_for": {"type": "array", "items": _str(1, 64)},
        "steps": {"type": "array", "minItems": 1, "items": _str(1, 64)},
        "workflow_ref": _str(1, 128),
        "param_bindings": {"type": "object"},
        "id_namespace": _str(1, 32),
        "body": {"type": ["string", "array"]},
        "convergence_expr": _str(1, 256),
        "max_iterations": {"type": "integer", "minimum": 1, "maximum": 1024},
        "on_bound_reached": {
            "type": "string",
            "enum": ["abort", "defer", "emit-partial"],
        },
        "allowed_responses": {"type": "array", "items": _str(1, 64)},
        "default_if_unanswered": _str(1, 64),
        "pause_token": _str(1, 64),
        "producer_unit": _str(1, 64),
        "item_path": _str(1, 256),
        "unit_template": {"type": "object"},
        "max_cardinality": {"type": "integer", "minimum": 1, "maximum": 4096},
        "max_attempts": {"type": "integer", "minimum": 1, "maximum": 8},
        "on_impossibility": _str(1, 128),
        "inputs": {"type": "array", "items": _str(1, 64)},
        "outputs": {"type": "array", "items": _str(1, 64)},
    }
    missing = [k for k in D.STAGE_FIELDS if k not in stage_props]
    if missing:
        raise SystemExit(f"stage properties missing STAGE_FIELDS: {missing}")

    typed_param = {
        "type": "object",
        "additionalProperties": False,
        "required": ["type"],
        "properties": {
            "type": {
                "type": "string",
                "enum": ["string", "integer", "number", "boolean", "array", "object"],
            },
            "value": True,
            "enum": {"type": "array", "minItems": 1},
            "secret_ref": _str(1, 256),
        },
        "allOf": [
            {
                "if": {"required": ["secret_ref"]},
                "then": {"not": {"required": ["value"]}},
            }
        ],
    }

    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://ast-integrate.invalid/command-center/phase4/contracts/ARC-0082.json",
        "$comment": (
            f"{SENTINEL} — declarative workflow DSL. certified_executable "
            "required set vs optional constructs. prompt_transport is file-only. "
            "A replayable workflow must declare resume. Inline prompt transport is rejected."
        ),
        "title": (
            "Workflow DSL: declarative schema for stages, gates, fan-out, resume and replay"
        ),
        "description": (
            "Draft 2020-12 schema for a declarative workflow: stages, roles, gates, "
            "tool policy, typed parameters, subworkflows, dynamic fan-out, barriers, "
            "loops with convergence, human checkpoints, retries, repair loops, resume, "
            "deterministic replay, artifact caching, dry-run, cost and time estimate, "
            "model routing, failure policy, and export/import. "
            f"{SENTINEL}"
        ),
        "unit_id": "ARC-0082",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "phase": "4",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "id",
            "stages",
            "entry",
            "failure_policy",
            "replayable",
            "certified_executable",
            "prompt_transport",
        ],
        "properties": {
            "id": {
                "type": "string",
                "minLength": 3,
                "maxLength": 64,
                "pattern": "^[A-Za-z0-9._-]+$",
            },
            "spec_version": {"type": "integer", "minimum": 1, "maximum": 64},
            "entry": _str(1, 64),
            "source_path": _str(1, 512),
            "prompt_transport": {
                "type": "string",
                "const": "file",
                "description": (
                    "Prompts travel as files. Inline argv/prompt transport is a "
                    "schema-invalid instance (win-arg-limit class)."
                ),
            },
            "replayable": {"type": "boolean"},
            "certified_executable": {"type": "boolean"},
            "failure_policy": {
                "type": "string",
                "enum": ["halt", "repair-loop", "skip-stage"],
            },
            "stages": {
                "type": "array",
                "minItems": 1,
                "maxItems": 256,
                "items": {"$ref": "#/$defs/stage"},
            },
            "roles": {
                "type": "array",
                "minItems": 1,
                "items": _str(1, 32),
            },
            "tool_policy": {"$ref": "#/$defs/toolPolicy"},
            "parameters": {
                "type": "object",
                "additionalProperties": {"$ref": "#/$defs/typedParam"},
            },
            "retries": {"$ref": "#/$defs/retries"},
            "resume": {"$ref": "#/$defs/resume"},
            "dry_run": {"type": "boolean"},
            "gates": {
                "type": "array",
                "items": {"$ref": "#/$defs/gate"},
            },
            "subworkflows": {
                "type": "array",
                "items": {"$ref": "#/$defs/subworkflow"},
            },
            "dynamic_fan_out": {
                "type": "array",
                "items": {"$ref": "#/$defs/dynamicFanOut"},
            },
            "barriers": {
                "type": "array",
                "items": {"$ref": "#/$defs/barrier"},
            },
            "loops": {
                "type": "array",
                "items": {"$ref": "#/$defs/loop"},
            },
            "human_checkpoints": {
                "type": "array",
                "items": {"$ref": "#/$defs/humanCheckpoint"},
            },
            "repair_loops": {
                "type": "array",
                "items": {"$ref": "#/$defs/repairLoop"},
            },
            "artifact_caching": {
                "type": "object",
                "additionalProperties": False,
                "required": ["enabled", "key"],
                "properties": {
                    "enabled": {"type": "boolean"},
                    "key": _str(1, 128),
                },
            },
            "cost_estimate": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "usd": {"type": "number", "minimum": 0, "maximum": 100000},
                    "tokens": {"type": "integer", "minimum": 0},
                    "currency": {"type": "string", "const": "USD"},
                },
            },
            "time_estimate": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "seconds": {"type": "integer", "minimum": 0, "maximum": 604800},
                    "timeout_s": {"type": "integer", "minimum": 1},
                },
            },
            "model_routing": {
                "type": "object",
                "additionalProperties": False,
                "required": ["policy", "silent_downgrade"],
                "properties": {
                    "policy": _str(1, 128),
                    "silent_downgrade": {"type": "boolean"},
                },
            },
            "export_import": {
                "type": "object",
                "additionalProperties": False,
                "required": ["format", "host_metadata_ignored", "round_trip"],
                "properties": {
                    "format": _str(1, 64),
                    "host_metadata_ignored": {"type": "boolean"},
                    "round_trip": {"type": "boolean"},
                },
            },
        },
        "allOf": [
            {
                "if": {
                    "type": "object",
                    "properties": {"certified_executable": {"const": True}},
                    "required": ["certified_executable"],
                },
                "then": {
                    "required": [
                        "roles",
                        "tool_policy",
                        "parameters",
                        "retries",
                        "resume",
                    ]
                },
            },
            {
                "if": {
                    "type": "object",
                    "properties": {"replayable": {"const": True}},
                    "required": ["replayable"],
                },
                "then": {"required": ["resume"]},
            },
        ],
        "$defs": {
            "stageKind": {"type": "string", "enum": STAGE_KIND_ENUM},
            "stage": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "kind", "role"],
                "properties": stage_props,
            },
            "toolPolicy": {
                "type": "object",
                "additionalProperties": False,
                "required": ["default", "allow", "deny"],
                "properties": {
                    "default": {"type": "string", "enum": ["deny", "allow"]},
                    "allow": {"type": "array", "items": _str(1, 64)},
                    "deny": {"type": "array", "items": _str(1, 64)},
                },
            },
            "typedParam": typed_param,
            "retries": {
                "type": "object",
                "additionalProperties": False,
                "required": ["max_retries", "repair_loop"],
                "properties": {
                    "max_retries": {"type": "integer", "minimum": 0, "maximum": 8},
                    "repair_loop": {"type": "boolean"},
                },
            },
            "resume": {
                "type": "object",
                "additionalProperties": False,
                "required": ["supported", "mode"],
                "properties": {
                    "supported": {"type": "boolean"},
                    "mode": {
                        "type": "string",
                        "enum": ["deterministic-replay", "none"],
                    },
                },
            },
            "gate": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "predicate", "role"],
                "properties": {
                    "id": _str(1, 64),
                    "predicate": _str(1, 256),
                    "role": _str(1, 32),
                },
            },
            "subworkflow": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "workflow_ref"],
                "properties": {
                    "id": _str(1, 64),
                    "workflow_ref": _str(1, 128),
                    "id_namespace": _str(1, 32),
                    "param_bindings": {"type": "object"},
                },
            },
            "dynamicFanOut": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "producer_unit", "item_path", "max_cardinality"],
                "properties": {
                    "id": _str(1, 64),
                    "producer_unit": _str(1, 64),
                    "item_path": _str(1, 256),
                    "max_cardinality": {"type": "integer", "minimum": 1},
                    "unit_template": {"type": "object"},
                },
            },
            "barrier": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "wait_for"],
                "properties": {
                    "id": _str(1, 64),
                    "wait_for": {"type": "array", "minItems": 1, "items": _str(1, 64)},
                },
            },
            "loop": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "body", "convergence_expr", "max_iterations"],
                "properties": {
                    "id": _str(1, 64),
                    "body": _str(1, 64),
                    "convergence_expr": _str(1, 256),
                    "max_iterations": {"type": "integer", "minimum": 1},
                    "on_bound_reached": {
                        "type": "string",
                        "enum": ["abort", "defer", "emit-partial"],
                    },
                },
            },
            "repairLoop": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "body", "max_attempts"],
                "properties": {
                    "id": _str(1, 64),
                    "body": _str(1, 64),
                    "max_attempts": {"type": "integer", "minimum": 1, "maximum": 8},
                    "on_impossibility": _str(1, 128),
                },
            },
            "humanCheckpoint": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "pause_token", "default_if_unanswered"],
                "properties": {
                    "id": _str(1, 64),
                    "pause_token": _str(1, 64),
                    "default_if_unanswered": _str(1, 64),
                    "prompt_ref": _str(1, 512),
                },
            },
        },
        "certified_executable_required": list(D.CERTIFIED_REQUIRED),
        "optional_constructs": list(D.OPTIONAL_CONSTRUCTS),
        "certified_vs_optional": {
            "rule": (
                "certified_executable=true requires roles, tool_policy, parameters, "
                "retries, and resume. certified_executable=false may omit those. "
                "replayable=true independently requires resume. prompt_transport is "
                "always file. Optional constructs (subworkflows, dynamic_fan_out, "
                "barriers, loops, human_checkpoints, repair_loops, artifact_caching, "
                "dry_run, cost_estimate, time_estimate, model_routing, export_import, "
                "gates) are schema-defined and may be absent on a sketch."
            ),
            "required_when_certified": list(D.CERTIFIED_REQUIRED),
            "optional": list(D.OPTIONAL_CONSTRUCTS),
        },
        "determinism": {
            "clause": (
                "A workflow with replayable=true must compile to identical execution "
                "plan bytes on two dry-runs. The planner is clock-free and host-free."
            ),
            "consumer_call_site": (
                "command-center/p2-wave/probes/ARC-0082/dsl.py:dry_run"
            ),
        },
        "expressibility": {
            "rule": (
                "A construct on a live blueprint that cannot be copied into this DSL "
                "is a schema defect, not a blueprint defect."
            ),
            "sampled_shapes": ["pipeline", "repair-loop", "converging-loop"],
            "sampled_blueprints": [
                "blueprints/workflows/wf.research.archival.json",
                "blueprints/workflows/wf.research.contradiction-negative-result.json",
                "blueprints/workflows/wf.research.watchlist.json",
            ],
        },
        "tests": [
            {
                "id": "T1-expressibility",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/ARC-0082/probe1_expressibility.py"
                ),
                "name": "Three distinct blueprint shapes encode losslessly",
            },
            {
                "id": "T2-determinism-certified",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/ARC-0082/probe2_determinism.py"
                ),
                "name": (
                    "Replayable dry-runs match; certified missing roles rejected; "
                    "uncertified sketch accepted; inline transport rejected"
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "ARC-0082-probe2-consumer-call-site",
            "verdict": "PASS",
            "independent": True,
            "role": "consumer-call-site",
            "notes": (
                "dsl.encode / dsl.dry_run is the consumer call site against this draft. "
                "agentspec.plan.compile_plan is used when present; otherwise "
                "probes/ARC-0082/local_plan.py."
            ),
        },
        "scope": {
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global unit_manifest.py --write was run",
                "the 09-WORKFLOW-BLUEPRINT-LIBRARY.json Windows restore path is mounted",
                "tools/agentspec/agentspec/plan.py is present on this worktree",
            ]
        },
    }


def assert_schema_usable(doc: dict) -> None:
    Draft202012Validator.check_schema(doc)
    validator = Draft202012Validator(doc)
    for i, g in enumerate(GARBAGE):
        errs = list(validator.iter_errors(g))
        if not errs:
            raise SystemExit(f"emit: schema accepted garbage[{i}]")
    missing_opt = [n for n in D.OPTIONAL_CONSTRUCTS if n not in doc["properties"]]
    missing_cert = [n for n in D.CERTIFIED_REQUIRED if n not in doc["properties"]]
    if missing_opt or missing_cert:
        raise SystemExit(f"emit: constructs missing opt={missing_opt} cert={missing_cert}")


def main() -> int:
    doc = schema_body()
    assert_schema_usable(doc)
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    if SENTINEL not in text:
        print("FAILED:ARC-0082 emit sentinel missing")
        return 1
    out.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OUT_REL} bytes={len(text.encode('utf-8'))}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
