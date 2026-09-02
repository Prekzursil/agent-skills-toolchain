"""Compile a CouncilSpec-shaped fixture onto the single workflow plane.

A council is a workflow type: kind=council, scheduler=agentspec. The compiler
emits FanOut/Barrier/Pipeline/Loop/Subworkflow/HumanCheckpoint/DynamicFanOut
nodes plus named same-plane extensions. It does not emit a CouncilEngine.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from plane import (
    ALLOWED_PRIMITIVES,
    EXTENSION_KINDS,
    HOME_PLANE,
    HOME_SCHEDULERS,
    NODE_KINDS,
    SCHEDULER_FEATURES,
    foreign_planes_in,
)

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"


def load_fixture(name: str) -> dict[str, Any]:
    path = FIX / name
    return json.loads(path.read_text(encoding="utf-8"))


def _truthy(spec: dict[str, Any], *keys: str) -> bool:
    for k in keys:
        v = spec.get(k)
        if v is True:
            return True
        if isinstance(v, (str, list, dict)) and v:
            return True
    return False


def _scheduler_name(spec: dict[str, Any]) -> str:
    for key in ("scheduler", "runtime", "control_plane", "engine"):
        val = spec.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return "agentspec"


def extra_scheduler_planes(spec: dict[str, Any]) -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []
    sched = _scheduler_name(spec).lower()
    if sched not in HOME_SCHEDULERS:
        hits.append(
            {
                "id": "non-home-scheduler",
                "plane": sched if sched not in {"langgraph"} else sched,
                "why": f"scheduler/runtime={sched!r} is not the agentspec plane",
            }
        )
    for feat in SCHEDULER_FEATURES:
        for field in feat["fields"]:
            if _truthy(spec, field):
                hits.append(
                    {
                        "id": feat["id"],
                        "plane": feat["plane"],
                        "why": feat["why"],
                        "field": field,
                    }
                )
                break
    nested = spec.get("nested") or spec.get("children")
    if nested and spec.get("child_runtime"):
        hits.append(
            {
                "id": "nested-private-runtime",
                "plane": "council-runtime",
                "why": "child councils must compile to Subworkflow, not child_runtime",
            }
        )
    return hits


def compile_council(spec: dict[str, Any]) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    extensions: set[str] = set()
    reasons: list[str] = []

    roles = spec.get("roles") or []
    if roles:
        nodes.append(
            {
                "id": "seats",
                "kind": "DynamicFanOut",
                "producer": "roles",
                "unit_template": "seat",
                "max_cardinality": max(1, len(roles)),
            }
        )
        nodes.append(
            {
                "id": "seat",
                "kind": "WorkUnit",
                "routing": True,
            }
        )

    for step in spec.get("protocol_schedule") or []:
        compose = str(step.get("compose") or "sequence")
        sid = str(step.get("id") or "step")
        if compose == "nest":
            nodes.append({"id": f"nest-{sid}", "kind": "Subworkflow", "protocol": sid})
        elif compose == "repeat-until":
            nodes.append(
                {
                    "id": f"repeat-{sid}",
                    "kind": "Loop",
                    "body": sid,
                    "max_iterations": int(step.get("max_iterations") or 8),
                    "convergence_expr": str(step.get("until") or "done"),
                }
            )
        elif compose == "splice":
            nodes.append({"id": f"splice-{sid}", "kind": "Pipeline", "splice": True})
        else:
            nodes.append({"id": f"seq-{sid}", "kind": "Pipeline", "protocol": sid})

    stopping = spec.get("stopping") or {}
    max_rounds = int(stopping.get("max_rounds") or 0)
    if max_rounds or stopping.get("expression"):
        nodes.append(
            {
                "id": "rounds",
                "kind": "Loop",
                "convergence_expr": str(stopping.get("expression") or "resolved"),
                "max_iterations": max_rounds or 8,
                "on_bound_reached": stopping.get("on_timeout") or "halt",
            }
        )

    # Divergence then convergence is a compile-time order, not a taste choice.
    if roles or spec.get("diverge", True):
        nodes.append({"id": "diverge", "kind": "FanOut", "from": "seats"})
        barrier: dict[str, Any] = {"id": "converge", "kind": "Barrier"}
        if spec.get("voting"):
            barrier["join"] = "BallotReduce"
            extensions.add("BallotReduce")
        elif spec.get("oracle"):
            barrier["join"] = "oracle_gate"
        else:
            barrier["join"] = "all-complete"
        nodes.append(barrier)

    order = [n["kind"] for n in nodes]
    if "Barrier" in order and "FanOut" in order:
        if order.index("Barrier") < order.index("FanOut"):
            reasons.append("convergence-before-divergence")

    if spec.get("anonymity"):
        extensions.add("BlindEnvelope")
        nodes.append({"id": "blind", "kind": "BlindEnvelope"})

    if spec.get("chair") or spec.get("owner_gate"):
        nodes.append(
            {
                "id": "owner-gate",
                "kind": "HumanCheckpoint",
                "pause_token": True,
                "default_if_unanswered": spec.get("default_if_unanswered"),
            }
        )

    if spec.get("nested") or spec.get("children"):
        nodes.append(
            {
                "id": "child-council",
                "kind": "Subworkflow",
                "workflow_ref": "kind:council",
                "id_namespace": "child",
            }
        )

    standing = bool(
        spec.get("standing_watch") or spec.get("wake_on") or spec.get("watch_loop")
    )
    if standing:
        extensions.add("Watch")
        nodes.append(
            {
                "id": "wake",
                "kind": "Watch",
                "wake_on": spec.get("wake_on") or ["etag"],
            }
        )

    if spec.get("oracle") and not any(n.get("join") == "oracle_gate" for n in nodes):
        nodes.append({"id": "oracle-join", "kind": "Barrier", "join": "oracle_gate"})

    kinds = {n["kind"] for n in nodes}
    unknown = sorted(kinds - NODE_KINDS - EXTENSION_KINDS)
    if unknown:
        reasons.append(f"unknown-node-kinds:{unknown}")

    foreign = foreign_planes_in(spec)
    sched_hits = extra_scheduler_planes(spec)
    extra_planes = sorted({HOME_PLANE} | set(foreign) | {h["plane"] for h in sched_hits})
    # count of orchestration planes the council introduces besides compiling onto home
    introduced = sorted(set(foreign) | {h["plane"] for h in sched_hits})
    count = 1 + len([p for p in introduced if p != HOME_PLANE])
    over_one = count > 1
    gate = "FIRE" if over_one or "convergence-before-divergence" in reasons else "PASS"

    named_scheduler_features = [
        {"id": h["id"], "plane": h["plane"], "why": h["why"]} for h in sched_hits
    ]
    if over_one and not named_scheduler_features and foreign:
        named_scheduler_features.append(
            {
                "id": "foreign-orchestrator",
                "plane": foreign[0],
                "why": "spec forbids importing a second orchestration runtime",
            }
        )

    return {
        "id": spec.get("id"),
        "kind": "council",
        "workflow_type": True,
        "home_plane": HOME_PLANE,
        "scheduler": "agentspec" if not over_one else _scheduler_name(spec),
        "nodes": nodes,
        "node_kinds": sorted(kinds),
        "extensions_named": sorted(extensions),
        "introduced_planes": introduced,
        "plane_count": count,
        "over_one": over_one,
        "gate": gate,
        "scheduler_features_named": named_scheduler_features,
        "reasons": reasons,
        "unknown_node_kinds": unknown,
        "uses_only_allowed_or_named_extension": not unknown
        and kinds <= (NODE_KINDS | EXTENSION_KINDS),
        "parallel_engine": over_one,
    }


def duplicate_probe(spec: dict[str, Any]) -> dict[str, Any]:
    compiled = compile_council(spec)
    return {
        "subject_id": spec.get("id"),
        "gate": compiled["gate"],
        "over_one": compiled["over_one"],
        "plane_count": compiled["plane_count"],
        "introduced_planes": compiled["introduced_planes"],
        "scheduler_features_named": compiled["scheduler_features_named"],
        "extensions_named": compiled["extensions_named"],
        "parallel_engine": compiled["parallel_engine"],
        "workflow_type": compiled["workflow_type"] and not compiled["over_one"],
        "compile": compiled,
    }
