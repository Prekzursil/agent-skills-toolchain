"""IMP-0195 probe 2 (verifier, two derivations of the same set): reachable-node
sets from iterative traversal and from Kahn topo + predecessor propagation are
EQUAL on the twin, the disconnected-node control, and the Loop x Barrier
fixture; the disconnected node is in NEITHER set.

Exit 0 iff parity holds on all three fixtures and the orphan is excluded.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(W / "tools" / "agentspec"))
from agentspec.spec import workflow_from_path  # noqa: E402
from agentspec.reachability import (control_successors, reachable_via_traversal,  # noqa: E402
                                    reachable_via_topo, analyze_reachability)

RAW = HERE / "probe2-derivation-parity.raw.txt"
FIX = HERE / "fixtures"


def both(wf):
    succs = control_successors(wf)
    ids = wf.node_id_set()
    trav = reachable_via_traversal(ids, succs, wf.entry)
    topo, cycle = reachable_via_topo(ids, succs, wf.entry)
    return trav, topo, cycle


twin = workflow_from_path(FIX / "reachable_twin.json")
disc = workflow_from_path(FIX / "disconnected_node.json")
loop = workflow_from_path(FIX / "loop_barrier.json")

twin_t, twin_p, twin_c = both(twin)
disc_t, disc_p, disc_c = both(disc)
loop_t, loop_p, loop_c = both(loop)

twin_equal = twin_t == twin_p and not twin_c
disconnected_equal = disc_t == disc_p and not disc_c
loop_equal = loop_t == loop_p and not loop_c

orphan = "orphan_pipe"
both_states_orphan_in_neither = (orphan not in disc_t) and (orphan not in disc_p)
twin_reachable = sorted(twin_t)
disconnected_reachable = sorted(disc_t - {orphan})
loop_reachable = sorted(loop_t)

distinct_functions = (reachable_via_traversal is not reachable_via_topo)

lines = [json.dumps({"probe": "probe2-derivation-parity", "unit_id": "IMP-0195",
                     "twin_equal": twin_equal, "twin_reachable": twin_reachable,
                     "disconnected_equal": disconnected_equal,
                     "disconnected_reachable": disconnected_reachable,
                     "disconnected_excluded": orphan,
                     "loop_equal": loop_equal, "loop_reachable": loop_reachable,
                     "both_states_orphan_in_neither": both_states_orphan_in_neither,
                     "derivations_distinct_functions": distinct_functions})]
assert twin_equal, "traversal and topo disagree on the twin"
assert disconnected_equal, "traversal and topo disagree on the disconnected control"
assert loop_equal, "traversal and topo disagree on the loop fixture"
assert both_states_orphan_in_neither, "orphan leaked into a reachable set"
assert loop_reachable == sorted(loop.node_id_set()), "loop body not fully reachable"
assert twin_reachable == sorted(twin.node_id_set()), "twin not fully reachable"
report = analyze_reachability(disc)
assert not report.accepted and report.unreachable_nodes == [orphan], report.as_dict()
RAW.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
print("RESULT:" + json.dumps({"twin": twin_reachable, "orphan_excluded": orphan,
                              "loop_body_reachable": True,
                              "parity_on_three_fixtures": True,
                              "derivations_distinct_functions": distinct_functions}))
print("SUCCESS:IMP-0195-probe2 traversal-vs-topo parity")
