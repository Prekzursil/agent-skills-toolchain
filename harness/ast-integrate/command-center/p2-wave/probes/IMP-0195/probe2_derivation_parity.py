#!/usr/bin/env python3
"""Probe 2: traversal-derived reachable set equals topological-sort-derived set.

Both-states on the set itself: a live node is in BOTH sets; a disconnected node
is in NEITHER. Equality alone would be silent if both derivations returned the
full node set (or both returned empty).
"""

from __future__ import annotations

import json

from paths import FIXDIR

from agentspec.reachability import (
    analyze_reachability,
    control_successors,
    reachable_via_topo,
    reachable_via_traversal,
)
from agentspec.spec import workflow_from_path
from agentspec.validate import validate_structural


def _fail(msg: str) -> int:
    print(f"FAILED:IMP-0195-probe2 {msg}")
    return 1


def _sets(wf):
    succs = control_successors(wf)
    ids = wf.node_id_set()
    trav = reachable_via_traversal(ids, succs, wf.entry)
    topo, cycle = reachable_via_topo(ids, succs, wf.entry)
    return trav, topo, cycle, succs


def main() -> int:
    twin = workflow_from_path(FIXDIR / "reachable_twin.json")
    disc = workflow_from_path(FIXDIR / "disconnected_node.json")
    looped = workflow_from_path(FIXDIR / "loop_barrier.json")

    for label, wf in (("twin", twin), ("disconnected", disc), ("loop", looped)):
        st = validate_structural(wf)
        if not st.ok:
            return _fail(f"{label} structural: {st.as_dict()}")

    t_trav, t_topo, t_cycle, _ = _sets(twin)
    if t_cycle:
        return _fail("reachable twin reported a cycle")
    if t_trav != t_topo:
        return _fail(f"twin derivation mismatch traversal={sorted(t_trav)} topo={sorted(t_topo)}")
    if t_trav != twin.node_id_set():
        return _fail(f"twin reachable {sorted(t_trav)} != all nodes {sorted(twin.node_id_set())}")
    if twin.entry not in t_trav or twin.entry not in t_topo:
        return _fail("entry missing from a derivation on the twin")

    d_trav, d_topo, d_cycle, _ = _sets(disc)
    if d_cycle:
        return _fail("disconnected fixture reported a cycle")
    if d_trav != d_topo:
        return _fail(
            f"disconnected derivation mismatch traversal={sorted(d_trav)} topo={sorted(d_topo)}"
        )
    if "orphan_pipe" in d_trav or "orphan_pipe" in d_topo:
        return _fail("disconnected node appeared in a reachable set")
    live = {"fan", "join", "pipe"}
    if not live.issubset(d_trav) or not live.issubset(d_topo):
        return _fail(f"live nodes missing from disconnected reachable set: {sorted(d_trav)}")
    if d_trav == disc.node_id_set():
        return _fail("disconnected derivation treated every node as reachable")

    l_trav, l_topo, l_cycle, _ = _sets(looped)
    if l_cycle:
        return _fail("loop fixture must remain a DAG (no back-edge in the static graph)")
    if l_trav != l_topo:
        return _fail(f"loop derivation mismatch traversal={sorted(l_trav)} topo={sorted(l_topo)}")
    if "body_pipe" not in l_trav:
        return _fail("loop body was not marked reachable from the loop node")

    r_twin = analyze_reachability(twin)
    r_disc = analyze_reachability(disc)
    r_loop = analyze_reachability(looped)
    if not r_twin.derivations_equal or not r_twin.accepted:
        return _fail(f"analyze twin: {r_twin.as_dict()}")
    if not r_disc.derivations_equal:
        return _fail(f"analyze disconnected derivations unequal: {r_disc.as_dict()}")
    if r_disc.accepted:
        return _fail("disconnected fixture was ACCEPTED; unreachable-node must reject")
    if "orphan_pipe" not in r_disc.unreachable_nodes:
        return _fail("orphan_pipe not in unreachable_nodes")
    if not r_loop.derivations_equal or not r_loop.accepted:
        return _fail(f"analyze loop: {r_loop.as_dict()}")

    # Detector control: calling the same function twice cannot certify independence.
    if reachable_via_traversal is reachable_via_topo:
        return _fail("the two derivations are the same object")
    if reachable_via_traversal.__code__ is reachable_via_topo.__code__:
        return _fail("the two derivations share a code object")

    report = {
        "twin_equal": True,
        "twin_reachable": sorted(t_trav),
        "disconnected_equal": True,
        "disconnected_reachable": sorted(d_trav),
        "disconnected_excluded": "orphan_pipe",
        "loop_equal": True,
        "loop_reachable": sorted(l_trav),
        "both_states_live_in_both": True,
        "both_states_orphan_in_neither": True,
        "derivations_distinct_functions": True,
    }
    print(json.dumps(report, sort_keys=True))
    print(
        f"equal=True twin={sorted(t_trav)} disconnected_excl=orphan_pipe "
        f"loop_body_reachable=True"
    )
    print("SUCCESS:IMP-0195-probe2 traversal-vs-topo parity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
