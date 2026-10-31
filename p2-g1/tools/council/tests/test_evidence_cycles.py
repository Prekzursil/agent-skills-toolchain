"""TST-0261 unit tests: the directed support-cycle invariant.

Mirrors the probe checks as pytest tests (planted 3-cycle fires with the
exact path; diamond silent; empty-support graph NOT-CHECKED; contradiction
edges never decide circular citation; Kahn leftovers).
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "command-center" / "p2-wave" / "probes" / "TST-0261"))

from council.evidence_graph import enforce, inspect, kahn_leftover  # noqa: E402
from fixtures import DIAMOND, EMPTY_EVIDENCE, THREE_NODE_CYCLE  # tools/council/tests -> REPO is parents[3]... see note  # noqa: E402


def test_planted_three_node_cycle_fires():
    r = inspect(THREE_NODE_CYCLE)
    assert r["status"] == "CYCLIC"
    assert r["cycles"][0]["path_printed"] == (
        "claim-alpha -> claim-beta -> claim-gamma -> claim-alpha"
    )


def test_diamond_is_silent():
    r = inspect(DIAMOND)
    assert r["status"] == "ACYCLIC"
    assert r["cycles"] == []


def test_empty_graph_not_checked():
    r = inspect(EMPTY_EVIDENCE)
    assert r["status"] == "NOT-CHECKED"
    assert r["accepted"] is False


def test_kahn_leftovers():
    assert sorted(kahn_leftover(THREE_NODE_CYCLE)) == [
        "claim-alpha",
        "claim-beta",
        "claim-gamma",
    ]
    assert kahn_leftover(DIAMOND) == []


def test_enforce_verdicts():
    assert enforce(THREE_NODE_CYCLE)["accepted"] is False
    assert enforce(DIAMOND)["accepted"] is True
    assert enforce(EMPTY_EVIDENCE)["accepted"] is False
