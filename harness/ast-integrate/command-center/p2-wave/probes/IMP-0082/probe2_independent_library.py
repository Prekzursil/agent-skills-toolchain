#!/usr/bin/env python3
"""Probe 2: independent graph library agreement + kind classification.

Evidence signal (2): stdlib graphlib.TopologicalSorter (and a Kosaraju SCC
pass) run over the same edge list agree with the primary detector on
existence AND membership. Optional and peer edges stay distinct from required.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from marketplace import cycle_cases as cases  # noqa: E402
from marketplace.cycle_ref import independent_report  # noqa: E402
from marketplace.dependency import (  # noqa: E402
    KIND_DEV,
    KIND_OPTIONAL,
    KIND_PEER,
    KIND_REQUIRED,
    cycle_matches,
    detect_cycles,
    graph_from_document,
    membership,
)


def _agree(doc, expected, members: set[str]) -> dict:
    g = graph_from_document(doc)
    found = detect_cycles(g)
    primary_members = membership(found)
    report = independent_report(g.pair_list())
    ok = (
        cycle_matches(found, expected)
        and report["graphlib"]["cyclic"] is True
        and set(report["members"]) == members
        and primary_members == members
        and report["internal_existence_agree"]
        and report["independent_existence"] is True
    )
    return {
        "ok": ok,
        "primary_paths": [list(c.path) for c in found],
        "primary_members": sorted(primary_members),
        "independent": report,
        "expected_members": sorted(members),
    }


def main() -> int:
    self_r = _agree(cases.self_cycle(), cases.EXPECTED_SELF, {"loop"})
    two_r = _agree(cases.two_node_cycle(), cases.EXPECTED_TWO, {"a", "b"})
    long_r = _agree(cases.long_cycle(), cases.EXPECTED_LONG, {"p", "q", "r", "s"})

    diamond_g = graph_from_document(cases.diamond())
    diamond_found = detect_cycles(diamond_g)
    diamond_ind = independent_report(diamond_g.pair_list())
    diamond_ok = (
        diamond_found == []
        and diamond_ind["graphlib"]["cyclic"] is False
        and diamond_ind["members"] == []
        and diamond_ind["independent_existence"] is False
    )

    kinds_g = graph_from_document(cases.kinds_distinct())
    by_kind = kinds_g.classify()
    kinds_ok = (
        by_kind[KIND_REQUIRED] == [("consumer", "lib-req", "^2.0.0")]
        and by_kind[KIND_OPTIONAL] == [("consumer", "lib-opt", "~1.4.0")]
        and by_kind[KIND_PEER] == [("consumer", "lib-peer", ">=3.0.0 <4.0.0")]
        and by_kind[KIND_DEV] == [("consumer", "lib-dev", "*")]
        and {e.kind for e in kinds_g.edges}
        == {KIND_REQUIRED, KIND_OPTIONAL, KIND_PEER, KIND_DEV}
        and detect_cycles(kinds_g) == []
    )

    peer_g = graph_from_document(cases.peer_only_mutual())
    peer_ok = (
        peer_g.classify()[KIND_REQUIRED] == []
        and detect_cycles(peer_g) == []
        and detect_cycles(peer_g, kinds=(KIND_PEER,)) != []
    )

    report = {
        "probe": "probe2-independent-library",
        "unit_id": "IMP-0082",
        "library": "graphlib.TopologicalSorter + Kosaraju SCC",
        "self_cycle": self_r,
        "two_node_cycle": two_r,
        "long_cycle": long_r,
        "diamond_negative_control": {
            "ok": diamond_ok,
            "primary_silent": diamond_found == [],
            "independent": diamond_ind,
        },
        "kinds_distinct_from_required": kinds_ok,
        "peer_only_mutual_not_install_cycle": peer_ok,
        "existence_and_membership_agree": all(
            [self_r["ok"], two_r["ok"], long_r["ok"], diamond_ok]
        ),
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    if not (
        self_r["ok"]
        and two_r["ok"]
        and long_r["ok"]
        and diamond_ok
        and kinds_ok
        and peer_ok
    ):
        print("FAILED:IMP-0082-probe2 independent library or kind classification")
        return 1
    print(
        "SUCCESS:IMP-0082-probe2 independent graphlib agrees on existence "
        "and membership; kinds distinct"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
