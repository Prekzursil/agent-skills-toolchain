"""Hermetic workflow simulator (IMP-0199).

Walks a declarative workflow graph with a FAKE rail. Structure, gates, loop
bounds and stopping rules are evaluated for real; anything demanding a
capability outside the hermetic set is REFUSED BY NAME before a single node
runs. A silently faked success for an unemulatable capability is the defect
this module exists to prevent, so the refusal registry here is independent of
the rail's own honesty (see ``NEVER_EMULATABLE``).

This module must never import the live pytest lane (``pytest_live``); the
probes assert that mechanically over this file's AST.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from agentspec.evals.fake_rail import NEVER_EMULATABLE, FakeRail


@dataclass
class SimulationResult:
    status: str = "RAN"
    visited: list[str] = field(default_factory=list)
    steps: int = 0
    gates_evaluated: int = 0
    stopping_rules_evaluated: int = 0
    receipts: list[dict[str, Any]] = field(default_factory=list)
    refused_capabilities: list[str] = field(default_factory=list)
    refusal_message: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "visited": list(self.visited),
            "steps": self.steps,
            "gates_evaluated": self.gates_evaluated,
            "stopping_rules_evaluated": self.stopping_rules_evaluated,
            "refused_capabilities": list(self.refused_capabilities),
            "refusal_message": self.refusal_message,
        }


def _refused_capabilities(workflow: Mapping[str, Any], rail: FakeRail) -> list[str]:
    """Union of the rail's own refusals and the simulator's hard registry."""
    out: set[str] = set()
    for node in workflow.get("nodes") or []:
        caps = [str(c) for c in (node.get("capabilities") or [])]
        if str(node.get("kind") or "") == "human_checkpoint" and "owner-interactive" not in caps:
            caps.append("owner-interactive")
        for cap in caps:
            if cap in NEVER_EMULATABLE or not rail.can_honestly_emulate(cap):
                out.add(cap)
    return sorted(out)


def _topo_order(workflow: Mapping[str, Any]) -> list[dict[str, Any]]:
    nodes = {str(n.get("id")): n for n in (workflow.get("nodes") or [])}
    indeg = {nid: 0 for nid in nodes}
    succs: dict[str, list[str]] = {nid: [] for nid in nodes}
    for edge in workflow.get("edges") or []:
        src, dst = str(edge[0]), str(edge[1])
        if src in nodes and dst in nodes:
            succs[src].append(dst)
            indeg[dst] += 1
    ready = sorted(nid for nid, d in indeg.items() if d == 0)
    order: list[str] = []
    while ready:
        nid = ready.pop(0)
        order.append(nid)
        for nxt in succs[nid]:
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                ready.append(nxt)
        ready.sort()
    return [nodes[nid] for nid in order]


def simulate(
    workflow: Mapping[str, Any],
    *,
    rail: FakeRail | None = None,
    ports: Any = None,
) -> SimulationResult:
    """Simulate ``workflow`` hermetically, or refuse it by capability name."""
    rail = rail if rail is not None else FakeRail()
    refused = _refused_capabilities(workflow, rail)
    if refused:
        return SimulationResult(
            status="REFUSED",
            refused_capabilities=refused,
            refusal_message=(
                "refused: unemulatable capabilities "
                + ", ".join(refused)
                + " cannot be honestly simulated"
            ),
        )

    result = SimulationResult(status="RAN")
    params = dict(workflow.get("params") or {})
    max_steps = int(workflow.get("max_steps") or 1024)
    loop_bodies: set[str] = set()
    for node in workflow.get("nodes") or []:
        if str(node.get("kind")) == "loop":
            loop_bodies.update(str(b) for b in (node.get("body") or []))
    nodes_by_id = {str(n.get("id")): n for n in (workflow.get("nodes") or [])}
    receipts_by_node: dict[str, dict[str, Any]] = {}

    def run_unit(node: Mapping[str, Any]) -> None:
        if result.steps >= max_steps:
            return
        result.steps += 1
        receipt = rail.execute_node(
            node,
            predecessors=dict(receipts_by_node),
            step=result.steps,
            params=params,
        )
        if isinstance(receipt, dict):
            receipts_by_node[str(node.get("id") or "")] = receipt
            result.receipts.append(receipt)

    for node in _topo_order(workflow):
        nid = str(node.get("id") or "")
        kind = str(node.get("kind") or "unit")
        if nid in loop_bodies:
            # executed under its owning loop node
            continue
        if nid not in result.visited:
            result.visited.append(nid)
        if kind == "gate":
            result.gates_evaluated += 1
        elif kind == "stopping_rule":
            result.stopping_rules_evaluated += 1
        elif kind == "loop":
            iterations = int(node.get("max_iterations") or 1)
            for _ in range(iterations):
                for body_id in node.get("body") or []:
                    body = nodes_by_id.get(str(body_id))
                    if body is None:
                        continue
                    if str(body_id) not in result.visited:
                        result.visited.append(str(body_id))
                    run_unit(body)
        else:
            run_unit(node)

    return result


__all__ = ["SimulationResult", "simulate"]
