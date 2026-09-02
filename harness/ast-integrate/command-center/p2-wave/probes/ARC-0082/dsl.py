#!/usr/bin/env python3
"""Consumer call site for ARC-0082: encode live blueprints and dry-run plans.

A construct on a source blueprint that cannot be copied into the DSL is a
schema defect (inexpressible), not a blueprint defect. Dry-run compiles the
encoded document through agentspec.plan.compile_plan. The planner is
clock-free and host-free; two dry-runs of a replayable workflow must match.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "agentspec"))

try:
    from agentspec.plan import compile_plan  # noqa: E402
    from agentspec.spec import KNOWN_NODE_KINDS, NODE_KEYS, WORKFLOW_KEYS  # noqa: E402
    from agentspec.determinism import canonical_bytes, canonical_sha256  # noqa: E402
except ImportError:
    from local_plan import (  # noqa: E402
        KNOWN_NODE_KINDS,
        NODE_KEYS,
        WORKFLOW_KEYS,
        canonical_bytes,
        canonical_sha256,
        compile_plan,
    )

CONTRACT_REL = "command-center/phase4/contracts/ARC-0082.json"
CONTRACT = REPO / CONTRACT_REL

BLUEPRINTS: tuple[tuple[str, str], ...] = (
    (
        "pipeline",
        "blueprints/workflows/wf.research.archival.json",
    ),
    (
        "repair-loop",
        "blueprints/workflows/wf.research.contradiction-negative-result.json",
    ),
    (
        "converging-loop",
        "blueprints/workflows/wf.research.watchlist.json",
    ),
)

STAGE_KIND_ALIASES = {
    "work": "WorkUnit",
    "fan-out": "FanOut",
    "barrier": "Barrier",
    "checkpoint": "HumanCheckpoint",
    "gate": "WorkUnit",
    "static-scan": "WorkUnit",
    "write-config": "WorkUnit",
}

ROLE_FOR_KIND = {
    "WorkUnit": "worker",
    "FanOut": "dispatcher",
    "Barrier": "synchronizer",
    "Pipeline": "orchestrator",
    "Subworkflow": "delegator",
    "Loop": "scheduler",
    "HumanCheckpoint": "human",
    "DynamicFanOut": "dispatcher",
    "RepairLoop": "repairer",
    "work": "worker",
    "gate": "gatekeeper",
    "checkpoint": "human",
    "fan-out": "dispatcher",
    "barrier": "synchronizer",
    "static-scan": "scanner",
    "write-config": "writer",
}

STAGE_FIELDS = (
    "id",
    "kind",
    "role",
    "max_retries",
    "prompt_ref",
    "params",
    "on_failure",
    "units",
    "wait_for",
    "steps",
    "workflow_ref",
    "param_bindings",
    "id_namespace",
    "body",
    "convergence_expr",
    "max_iterations",
    "on_bound_reached",
    "allowed_responses",
    "default_if_unanswered",
    "pause_token",
    "producer_unit",
    "item_path",
    "unit_template",
    "max_cardinality",
    "max_attempts",
    "on_impossibility",
    "inputs",
    "outputs",
)

OPTIONAL_CONSTRUCTS = (
    "subworkflows",
    "dynamic_fan_out",
    "barriers",
    "loops",
    "human_checkpoints",
    "repair_loops",
    "artifact_caching",
    "dry_run",
    "cost_estimate",
    "time_estimate",
    "model_routing",
    "export_import",
    "gates",
)

CERTIFIED_REQUIRED = (
    "id",
    "stages",
    "entry",
    "roles",
    "tool_policy",
    "parameters",
    "failure_policy",
    "retries",
    "resume",
    "replayable",
    "prompt_transport",
)

STRIP_FROM_NODES = frozenset({"role", "max_retries", "inputs", "outputs"})


def load_contract() -> dict[str, Any]:
    text = CONTRACT.read_text(encoding="utf-8")
    if "SUCCESS:ARC-0082" not in text:
        raise ValueError("sentinel-absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        raise ValueError(f"self-declared:{doc.get('state')}")
    Draft202012Validator.check_schema(doc)
    return doc


def validator(schema: dict[str, Any] | None = None) -> Draft202012Validator:
    return Draft202012Validator(schema if schema is not None else load_contract())


def validate_instance(
    instance: Mapping[str, Any], schema: dict[str, Any] | None = None
) -> list[str]:
    v = validator(schema)
    return sorted({e.message for e in v.iter_errors(instance)})


def load_blueprint(rel: str) -> dict[str, Any]:
    path = REPO / rel
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise TypeError(f"{rel} is not an object")
    return doc


def _param_type(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int) and not isinstance(value, bool):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "string"


def _typed_params(raw_params: Any) -> dict[str, Any]:
    if not isinstance(raw_params, Mapping):
        return {}
    out: dict[str, Any] = {}
    for key, value in raw_params.items():
        item: dict[str, Any] = {"type": _param_type(value), "value": value}
        if isinstance(value, str) and value in {"one-shot", "scheduled"}:
            item["enum"] = ["one-shot", "scheduled"]
        out[str(key)] = item
    return out


def _failure_policy(entry: Mapping[str, Any]) -> str:
    kind = str(entry.get("kind") or "")
    if kind == "RepairLoop":
        return "repair-loop"
    policy = entry.get("on_failure")
    if isinstance(policy, str) and policy in {"continue", "quarantine"}:
        return "skip-stage"
    if isinstance(policy, Mapping):
        actions = {str(v) for v in policy.values()}
        if actions <= {"continue", "quarantine"}:
            return "skip-stage"
        if "repair" in actions and kind in {"RepairLoop", "Loop"}:
            return "repair-loop"
    return "halt"


def _expand_on_failure(raw: Any) -> dict[str, str] | None:
    families = (
        "adapter-exit-n",
        "blocked",
        "degraded",
        "partial-artifact",
        "schema-invalid",
        "severed-stream",
        "timeout",
        "win-arg-limit",
    )
    actions = {"abort", "continue", "escalate", "quarantine", "repair"}
    if isinstance(raw, str) and raw in actions:
        return {f: raw for f in families}
    if isinstance(raw, Mapping) and set(raw) >= set(families):
        out = {f: str(raw[f]) for f in families}
        if set(out.values()) <= actions:
            return out
    return None


def inexpressible(raw: Mapping[str, Any]) -> list[str]:
    """Itemize source constructs the DSL cannot copy. Empty means expressible."""
    missing: list[str] = []
    schema = load_contract()
    stage_props = set(
        ((schema.get("$defs") or {}).get("stage") or {}).get("properties") or {}
    )
    kind_enum = list(
        ((schema.get("$defs") or {}).get("stageKind") or {}).get("enum") or []
    )
    nodes = raw.get("nodes") if isinstance(raw.get("nodes"), list) else raw.get("stages")
    if not isinstance(nodes, list) or not nodes:
        missing.append("workflow.nodes-or-stages")
        return missing
    for i, node in enumerate(nodes):
        if not isinstance(node, Mapping):
            missing.append(f"nodes[{i}]:not-object")
            continue
        kind = node.get("kind")
        if kind not in kind_enum:
            missing.append(f"kind:{kind}")
        for key in node:
            if key in {"id", "kind"}:
                continue
            if key not in stage_props and key not in STAGE_FIELDS:
                missing.append(f"{node.get('id', i)}.{key}")
            elif key not in stage_props:
                missing.append(f"{node.get('id', i)}.{key}")
        if kind in KNOWN_NODE_KINDS:
            allowed = NODE_KEYS[str(kind)]
            extra = set(node) - set(allowed)
            # extras must still be named as expressible stage fields
            for key in sorted(extra):
                if key not in stage_props:
                    missing.append(f"{node.get('id', i)}.{key}:closed-set")
    extra_wf = set(raw) - set(WORKFLOW_KEYS) - {"_generated", "discovery_only"}
    for key in sorted(extra_wf):
        # Workflow-level extras are optional metadata; only fail if they
        # look like control-flow constructs the DSL omitted.
        if key in {
            "fan_out",
            "repair_loop",
            "subworkflow",
            "checkpoint",
            "barrier",
        }:
            missing.append(f"workflow.{key}")
    return missing


def encode(
    raw: Mapping[str, Any],
    *,
    source_path: str,
    certified: bool = True,
    replayable: bool = True,
) -> dict[str, Any]:
    nodes = raw.get("nodes") if isinstance(raw.get("nodes"), list) else raw.get("stages")
    if not isinstance(nodes, list) or not nodes:
        raise ValueError("blueprint has no nodes/stages")
    by_id = {
        str(n.get("id")): n
        for n in nodes
        if isinstance(n, Mapping) and isinstance(n.get("id"), str)
    }
    entry_id = str(raw.get("entry") or next(iter(by_id)))
    entry = by_id.get(entry_id) or next(iter(by_id.values()))

    stages: list[dict[str, Any]] = []
    roles: list[str] = []
    loops: list[dict[str, Any]] = []
    repair_loops: list[dict[str, Any]] = []
    barriers: list[dict[str, Any]] = []
    fan_outs: list[dict[str, Any]] = []
    subworkflows: list[dict[str, Any]] = []
    human_checkpoints: list[dict[str, Any]] = []
    dynamic_fan_out: list[dict[str, Any]] = []
    gates: list[dict[str, Any]] = []
    max_retries = 0

    for node in nodes:
        if not isinstance(node, Mapping):
            continue
        kind = str(node.get("kind") or "WorkUnit")
        role = ROLE_FOR_KIND.get(kind, "worker")
        stage: dict[str, Any] = {
            "id": str(node.get("id") or ""),
            "kind": kind,
            "role": role,
        }
        of = _expand_on_failure(node.get("on_failure"))
        if of is not None:
            stage["on_failure"] = of
        for key in STAGE_FIELDS:
            if key in {"id", "kind", "role", "on_failure", "max_retries"}:
                continue
            if key in node:
                stage[key] = node[key]
        if kind == "RepairLoop":
            attempts = int(node.get("max_attempts") or 0)
            stage["max_retries"] = min(max(attempts, 0), 8)
            max_retries = max(max_retries, stage["max_retries"])
        elif isinstance(node.get("max_retries"), int):
            stage["max_retries"] = min(max(int(node["max_retries"]), 0), 8)
            max_retries = max(max_retries, stage["max_retries"])
        stages.append(stage)
        if role not in roles:
            roles.append(role)
        if kind == "Loop":
            loops.append(
                {
                    "id": stage["id"],
                    "body": str(stage.get("body") or ""),
                    "convergence_expr": str(stage.get("convergence_expr") or "checkpoint_persisted"),
                    "max_iterations": int(stage.get("max_iterations") or 1),
                    **(
                        {"on_bound_reached": stage["on_bound_reached"]}
                        if "on_bound_reached" in stage
                        else {}
                    ),
                }
            )
        elif kind == "RepairLoop":
            repair_loops.append(
                {
                    "id": stage["id"],
                    "body": str(stage.get("body") or ""),
                    "max_attempts": int(stage.get("max_attempts") or 1),
                    **(
                        {"on_impossibility": stage["on_impossibility"]}
                        if "on_impossibility" in stage
                        else {}
                    ),
                }
            )
        elif kind in {"Barrier", "barrier"}:
            barriers.append(
                {"id": stage["id"], "wait_for": list(stage.get("wait_for") or [])}
            )
        elif kind in {"FanOut", "fan-out"}:
            fan_outs.append({"id": stage["id"], "units": list(stage.get("units") or [])})
        elif kind == "DynamicFanOut":
            dynamic_fan_out.append(
                {
                    "id": stage["id"],
                    "producer_unit": str(stage.get("producer_unit") or ""),
                    "item_path": str(stage.get("item_path") or ""),
                    "max_cardinality": int(stage.get("max_cardinality") or 1),
                    **(
                        {"unit_template": dict(stage["unit_template"])}
                        if isinstance(stage.get("unit_template"), Mapping)
                        else {}
                    ),
                }
            )
        elif kind == "Subworkflow":
            subworkflows.append(
                {
                    "id": stage["id"],
                    "workflow_ref": str(stage.get("workflow_ref") or ""),
                    **(
                        {"id_namespace": stage["id_namespace"]}
                        if "id_namespace" in stage
                        else {}
                    ),
                    **(
                        {"param_bindings": dict(stage["param_bindings"])}
                        if isinstance(stage.get("param_bindings"), Mapping)
                        else {}
                    ),
                }
            )
        elif kind in {"HumanCheckpoint", "checkpoint"}:
            human_checkpoints.append(
                {
                    "id": stage["id"],
                    "pause_token": str(stage.get("pause_token") or stage["id"]),
                    "default_if_unanswered": str(
                        stage.get("default_if_unanswered") or "defer"
                    ),
                    **(
                        {"prompt_ref": stage["prompt_ref"]}
                        if "prompt_ref" in stage
                        else {}
                    ),
                }
            )
        elif kind == "gate":
            gates.append(
                {
                    "id": stage["id"],
                    "predicate": str(stage.get("prompt_ref") or "gate"),
                    "role": role,
                }
            )

    encoded: dict[str, Any] = {
        "id": str(raw.get("id") or "unnamed-workflow")[:64],
        "spec_version": int(raw.get("spec_version") or 11),
        "entry": entry_id,
        "source_path": source_path,
        "prompt_transport": "file",
        "replayable": bool(replayable),
        "certified_executable": bool(certified),
        "failure_policy": _failure_policy(entry if isinstance(entry, Mapping) else {}),
        "stages": stages,
        "dry_run": True,
    }
    if certified:
        encoded["roles"] = roles or ["worker"]
        encoded["tool_policy"] = {
            "default": "deny",
            "allow": ["prompt-file-read"],
            "deny": ["credential-wildcard"],
        }
        encoded["parameters"] = _typed_params(raw.get("params"))
        encoded["retries"] = {
            "max_retries": max_retries,
            "repair_loop": any(s.get("kind") == "RepairLoop" for s in stages),
        }
        encoded["resume"] = {
            "supported": True,
            "mode": "deterministic-replay" if replayable else "none",
        }
        encoded["artifact_caching"] = {
            "enabled": True,
            "key": "workflow-id+resolved-inputs",
        }
        encoded["export_import"] = {
            "format": "agentspec.replay.v1",
            "host_metadata_ignored": True,
            "round_trip": True,
        }
        encoded["model_routing"] = {
            "policy": "declared-on-stage-or-absent",
            "silent_downgrade": False,
        }
    elif replayable:
        encoded["resume"] = {"supported": True, "mode": "deterministic-replay"}
    if loops:
        encoded["loops"] = loops
    if repair_loops:
        encoded["repair_loops"] = repair_loops
    if barriers:
        encoded["barriers"] = barriers
    if fan_outs:
        encoded["dynamic_fan_out"] = encoded.get("dynamic_fan_out") or []
        # static FanOut stays in stages; optional construct slot remains defined
    if dynamic_fan_out:
        encoded["dynamic_fan_out"] = dynamic_fan_out
    if subworkflows:
        encoded["subworkflows"] = subworkflows
    if human_checkpoints:
        encoded["human_checkpoints"] = human_checkpoints
    if gates:
        encoded["gates"] = gates
    return encoded


def to_agentspec(encoded: Mapping[str, Any]) -> dict[str, Any]:
    """Project a DSL instance onto the closed AgentSpec workflow keys."""
    nodes: list[dict[str, Any]] = []
    for stage in encoded.get("stages") or []:
        if not isinstance(stage, Mapping):
            continue
        kind = str(stage.get("kind") or "")
        agentspec_kind = STAGE_KIND_ALIASES.get(kind, kind)
        node: dict[str, Any] = {
            "id": str(stage.get("id") or ""),
            "kind": agentspec_kind,
        }
        allowed = NODE_KEYS.get(agentspec_kind, frozenset({"id", "kind"}))
        for key, value in stage.items():
            if key in STRIP_FROM_NODES:
                continue
            if key in {"id", "kind"}:
                continue
            if key in allowed:
                node[key] = value
        nodes.append(node)
    params: dict[str, Any] = {}
    raw_params = encoded.get("parameters") or {}
    if isinstance(raw_params, Mapping):
        for key, spec in raw_params.items():
            if isinstance(spec, Mapping) and "value" in spec:
                params[str(key)] = spec["value"]
    wf = {
        "id": str(encoded.get("id") or ""),
        "spec_version": int(encoded.get("spec_version") or 11),
        "entry": str(encoded.get("entry") or ""),
        "params": params,
        "nodes": nodes,
    }
    return wf


def dry_run(encoded: Mapping[str, Any]) -> dict[str, Any]:
    """Compile a host-free execution plan. Same input => same plan bytes."""
    wf = to_agentspec(encoded)
    plan = compile_plan(wf)
    return {
        "plan": plan,
        "sha256": canonical_sha256(plan),
        "bytes": canonical_bytes(plan).decode("utf-8"),
        "kinds": [s.get("kind") for s in plan],
        "workflow_id": wf.get("id"),
        "entry": wf.get("entry"),
    }


def encode_corpus() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    schema = load_contract()
    for shape, rel in BLUEPRINTS:
        raw = load_blueprint(rel)
        missing = inexpressible(raw)
        encoded = encode(raw, source_path=rel)
        errors = validate_instance(encoded, schema)
        plan = dry_run(encoded)
        raw_plan = compile_plan(raw)
        rows.append(
            {
                "shape": shape,
                "source_path": rel,
                "id": encoded.get("id"),
                "inexpressible": missing,
                "schema_errors": errors,
                "plan_sha256": plan["sha256"],
                "raw_plan_sha256": canonical_sha256(raw_plan),
                "plan_kinds": plan["kinds"],
                "encoded": encoded,
            }
        )
    return rows


def schema_constructs() -> dict[str, bool]:
    props = set((load_contract().get("properties") or {}).keys())
    return {
        "optional_defined": all(name in props for name in OPTIONAL_CONSTRUCTS),
        "certified_defined": all(name in props for name in CERTIFIED_REQUIRED),
        "missing_optional": [n for n in OPTIONAL_CONSTRUCTS if n not in props],
        "missing_certified": [n for n in CERTIFIED_REQUIRED if n not in props],
    }
