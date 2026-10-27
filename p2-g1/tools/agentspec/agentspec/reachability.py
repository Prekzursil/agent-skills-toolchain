"""Node reachability over the control graph, derived TWO independent ways.

``reachable_via_traversal`` walks the successor map from the entry node;
``reachable_via_topo`` propagates a reachability flag along a Kahn topological
order. They are deliberately distinct implementations (distinct code objects):
equality between two runs of the SAME function certifies nothing.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Iterable, Mapping


def control_successors(workflow) -> dict[str, list[str]]:
    """Control-flow successor map: ``next`` pointers plus loop bodies."""
    node_ids = {n.id for n in workflow.nodes}
    succs: dict[str, list[str]] = {nid: [] for nid in node_ids}
    for node in workflow.nodes:
        nxt = getattr(node, "next", None)
        if nxt and nxt in node_ids and nxt not in succs[node.id]:
            succs[node.id].append(nxt)
        for body_id in getattr(node, "body", ()) or ():
            if body_id in node_ids and body_id not in succs[node.id]:
                succs[node.id].append(str(body_id))
    return succs


def reachable_via_traversal(
    ids: Iterable[str], succs: Mapping[str, Iterable[str]], entry: str | None
) -> set[str]:
    """Breadth-first walk of the successor map from ``entry``."""
    ids = set(ids)
    if entry is None or entry not in ids:
        return set()
    seen: set[str] = {entry}
    queue: deque[str] = deque([entry])
    while queue:
        nid = queue.popleft()
        for nxt in succs.get(nid, ()):  # type: ignore[call-overload]
            if nxt in ids and nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return seen


def reachable_via_topo(
    ids: Iterable[str], succs: Mapping[str, Iterable[str]], entry: str | None
) -> tuple[set[str], bool]:
    """Kahn topological order with a propagated reachability flag.

    Returns ``(reachable_set, cycle_detected)``. On a cycle the returned set
    covers only what the acyclic prefix could prove reachable.
    """
    ids = set(ids)
    indeg: dict[str, int] = {nid: 0 for nid in ids}
    for src in ids:
        for dst in succs.get(src, ()):  # type: ignore[call-overload]
            if dst in indeg:
                indeg[dst] += 1
    ready = sorted(nid for nid, d in indeg.items() if d == 0)
    order: list[str] = []
    while ready:
        nid = ready.pop(0)
        order.append(nid)
        for dst in succs.get(nid, ()):  # type: ignore[call-overload]
            if dst in indeg:
                indeg[dst] -= 1
                if indeg[dst] == 0:
                    ready.append(dst)
        ready.sort()
    cycle = len(order) != len(ids)
    reachable: set[str] = set()
    if entry is not None and entry in ids:
        reachable.add(entry)
        for nid in order:
            if nid not in reachable:
                continue
            for dst in succs.get(nid, ()):  # type: ignore[call-overload]
                if dst in ids:
                    reachable.add(dst)
    return reachable, cycle


@dataclass
class ReachabilityReport:
    derivations_equal: bool
    accepted: bool
    cycle: bool
    entry: str | None
    reachable: list[str] = field(default_factory=list)
    unreachable_nodes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "derivations_equal": self.derivations_equal,
            "accepted": self.accepted,
            "cycle": self.cycle,
            "entry": self.entry,
            "reachable": list(self.reachable),
            "unreachable_nodes": list(self.unreachable_nodes),
        }


def analyze_reachability(workflow) -> ReachabilityReport:
    """Both derivations plus the accept/reject verdict for the workflow graph."""
    succs = control_successors(workflow)
    ids = workflow.node_id_set()
    trav = reachable_via_traversal(ids, succs, workflow.entry)
    topo, cycle = reachable_via_topo(ids, succs, workflow.entry)
    equal = trav == topo
    unreachable = sorted(ids - trav)
    accepted = bool(equal and not cycle and not unreachable)
    return ReachabilityReport(
        derivations_equal=equal,
        accepted=accepted,
        cycle=cycle,
        entry=workflow.entry,
        reachable=sorted(trav),
        unreachable_nodes=unreachable,
    )


__all__ = [
    "ReachabilityReport",
    "analyze_reachability",
    "control_successors",
    "reachable_via_topo",
    "reachable_via_traversal",
]
