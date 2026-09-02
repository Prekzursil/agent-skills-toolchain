"""Deterministic workflow DAG replay for Phase-7 fixtures (FanOut/Barrier/DynamicFanOut).

Ready-set order is id-stable unless Host.leak_pid_into_ready. DynamicFanOut width is
2+(seed%3) unless Host.leak_clock_into_fanout, which folds now_ns into the width.
"""

from __future__ import annotations

import hashlib
from typing import Any

from canonical_trace import digest_trace


def ready_sort_key(node_id: str, host: Any) -> tuple[str, str]:
    if getattr(host, "leak_pid_into_ready", False):
        digest = hashlib.sha256(f"{host.pid()}:{node_id}".encode("utf-8")).hexdigest()
        return (digest, node_id)
    return ("", node_id)


def _dyn_cardinality(node: dict[str, Any], host: Any) -> int:
    cap = int(node.get("max_cardinality") or 8)
    base = 2 + (int(host.seed) % 3)
    if getattr(host, "leak_clock_into_fanout", False):
        ns = int(host.now_ns())
        extra = 0 if ns == 0 else 1 + (ns % 3)
        base = 2 + extra
    if base < 1:
        base = 1
    if base > cap:
        base = cap
    return base


def _template_id(node: dict[str, Any]) -> str:
    raw = node.get("unit_template")
    if isinstance(raw, dict):
        return str(raw.get("id") or "task")
    if isinstance(raw, str) and raw:
        return raw
    return "task"


def replay_workflow(workflow: dict[str, Any], host: Any) -> dict[str, Any]:
    nodes = list(workflow.get("nodes") or [])
    by_id: dict[str, dict[str, Any]] = {}
    for node in nodes:
        nid = str(node.get("id") or "")
        if nid:
            by_id[nid] = node

    fan_members: dict[str, set[str]] = {}
    for node in nodes:
        kind = str(node.get("type") or "")
        if kind == "FanOut":
            members = [str(x) for x in (node.get("unit_ids") or node.get("units") or [])]
            fan_members[str(node["id"])] = set(members)

    unit_to_fan: dict[str, str] = {}
    for fid, members in fan_members.items():
        for uid in members:
            unit_to_fan[uid] = fid

    pending: set[str] = set(by_id)
    done: set[str] = set()
    children: dict[str, list[str]] = {}
    node_order: list[str] = []
    fan_out: list[dict[str, Any]] = []
    barriers: list[dict[str, Any]] = []
    steps: list[dict[str, Any]] = []

    def ready() -> list[str]:
        out: list[str] = []
        for nid in pending:
            node = by_id[nid]
            kind = str(node.get("type") or "")
            if kind == "FanOut":
                out.append(nid)
                continue
            if kind == "DynamicFanOut":
                producer = str(node.get("producer_unit") or "")
                if producer in done:
                    out.append(nid)
                continue
            if kind == "Barrier":
                waits = [str(x) for x in (node.get("wait_for") or node.get("awaits") or [])]
                if waits and all(w in done for w in waits):
                    out.append(nid)
                continue
            fan = unit_to_fan.get(nid)
            if fan is None or fan in done:
                out.append(nid)
        return sorted(out, key=lambda n: ready_sort_key(n, host))

    guard = 0
    while pending:
        guard += 1
        if guard > 10_000:
            raise RuntimeError(f"replay did not terminate pending={sorted(pending)}")
        batch = ready()
        if not batch:
            raise RuntimeError(f"deadlock pending={sorted(pending)} done={sorted(done)}")
        nid = batch[0]
        node = by_id[nid]
        kind = str(node.get("type") or "")
        pending.remove(nid)
        node_order.append(nid)
        steps.append({"id": nid, "kind": kind or "WorkUnit"})

        if kind == "FanOut":
            members = sorted(fan_members.get(nid) or [])
            fan_out.append({"id": nid, "kind": "FanOut", "cardinality": len(members)})
        elif kind == "DynamicFanOut":
            card = _dyn_cardinality(node, host)
            template = _template_id(node)
            spawned = [f"{template}#{i}" for i in range(card)]
            children[nid] = spawned
            for cid in spawned:
                by_id[cid] = {
                    "id": cid,
                    "type": "WorkUnit",
                    "from_dynamic": nid,
                }
                pending.add(cid)
            fan_out.append({"id": nid, "kind": "DynamicFanOut", "cardinality": card})
        elif kind == "Barrier":
            waits = [str(x) for x in (node.get("wait_for") or node.get("awaits") or [])]
            barriers.append({"id": nid, "wait_for": waits, "resolved": True})

        done.add(nid)

    trace = {
        "barrier_resolution": barriers,
        "fan_out": fan_out,
        "node_order": node_order,
    }
    return {
        "trace": trace,
        "trace_hash": digest_trace(trace),
        "steps": steps,
        "children": children,
    }
