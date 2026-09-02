"""Unit tests for tools/council/evidence_graph.py (TST-0261): circular-citation detection.

Three planted council graphs, both states of the detector:

* a 3-node support cycle ``claim-alpha -> claim-beta -> claim-gamma -> claim-alpha`` --
  the detector must FIRE and print exactly that closed path;
* a diamond (two long support chains sharing the ancestor ``ev-root``) -- a DAG, so the
  detector must stay SILENT; a detector that flags a diamond is unusable;
* a council with claims and a contradiction pair but zero support edges -- ``NOT-CHECKED``,
  never ``ACYCLIC`` and never ``accepted``; the contradiction 2-cycle is not a citation.

Each ``test_*`` function raises ``AssertionError`` on failure and returns a small
JSON-serialisable observation so a probe can call it directly and record what it saw.
The ``unittest`` class at the bottom wraps the same functions for the test runner.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.council.evidence_graph import (  # noqa: E402
    STATUS_ACYCLIC,
    STATUS_CYCLIC,
    STATUS_NOT_CHECKED,
    CyclicEvidenceError,
    EmptyEvidenceError,
    enforce,
    inspect,
)

# Node ids and edge order are part of the contract: the printed path must be exact.
CLAIM_ALPHA = "claim-alpha"
CLAIM_BETA = "claim-beta"
CLAIM_GAMMA = "claim-gamma"
THREE_CYCLE_PATH = [CLAIM_ALPHA, CLAIM_BETA, CLAIM_GAMMA, CLAIM_ALPHA]
THREE_CYCLE_PRINTED = "claim-alpha -> claim-beta -> claim-gamma -> claim-alpha"

EV_ROOT = "ev-root"
EV_LEFT = "ev-left"
EV_RIGHT = "ev-right"
MID_1, MID_2, MID_3, MID_4 = "mid-1", "mid-2", "mid-3", "mid-4"
CLAIM_TIP = "claim-tip"


def planted_three_node_cycle() -> dict[str, Any]:
    """Cites-loop of length 3: alpha cites beta cites gamma cites alpha."""
    return {
        "nodes": [
            {"id": CLAIM_ALPHA, "kind": "claim"},
            {"id": CLAIM_BETA, "kind": "claim"},
            {"id": CLAIM_GAMMA, "kind": "claim"},
        ],
        "support_edges": [
            {"from": CLAIM_ALPHA, "to": CLAIM_BETA},
            {"from": CLAIM_BETA, "to": CLAIM_GAMMA},
            {"from": CLAIM_GAMMA, "to": CLAIM_ALPHA},
        ],
        "contradiction_edges": [],
    }


def planted_diamond_long_chain() -> dict[str, Any]:
    """Two long support chains from claim-tip that share the ancestor ev-root: a DAG."""
    return {
        "nodes": [
            {"id": CLAIM_TIP, "kind": "claim"},
            {"id": MID_1, "kind": "claim"},
            {"id": MID_2, "kind": "claim"},
            {"id": MID_3, "kind": "claim"},
            {"id": MID_4, "kind": "claim"},
            {"id": EV_LEFT, "kind": "evidence"},
            {"id": EV_RIGHT, "kind": "evidence"},
            {"id": EV_ROOT, "kind": "evidence"},
        ],
        "support_edges": [
            {"from": CLAIM_TIP, "to": MID_1},
            {"from": MID_1, "to": MID_2},
            {"from": MID_2, "to": EV_LEFT},
            {"from": EV_LEFT, "to": EV_ROOT},
            {"from": CLAIM_TIP, "to": MID_3},
            {"from": MID_3, "to": MID_4},
            {"from": MID_4, "to": EV_RIGHT},
            {"from": EV_RIGHT, "to": EV_ROOT},
        ],
        "contradiction_edges": [],
    }


def planted_empty_evidence() -> dict[str, Any]:
    """Claims and a mutual contradiction pair, but zero support edges."""
    return {
        "nodes": [
            {"id": CLAIM_ALPHA, "kind": "claim"},
            {"id": CLAIM_BETA, "kind": "claim"},
            {"id": CLAIM_GAMMA, "kind": "claim"},
        ],
        "support_edges": [],
        "contradiction_edges": [
            {"from": CLAIM_ALPHA, "to": CLAIM_BETA},
            {"from": CLAIM_BETA, "to": CLAIM_ALPHA},
        ],
    }


def _walk_support(graph: dict[str, Any], start: str, steps: int) -> list[str]:
    """Follow support edges from ``start`` without the detector (independent oracle)."""
    nxt = {e["from"]: e["to"] for e in graph["support_edges"]}
    path = [start]
    cur = start
    for _ in range(steps):
        cur = nxt[cur]
        path.append(cur)
    return path


def test_planted_three_node_cycle_fires() -> dict[str, Any]:
    """The 3-node citation loop FIRES with the exact closed path, and ``enforce`` refuses."""
    graph = planted_three_node_cycle()
    report = inspect(graph)
    assert report["status"] == STATUS_CYCLIC, f"3-cycle status={report['status']}"
    assert report["accepted"] is False, "a cyclic graph must not be accepted"
    assert report["cycle_count"] == 1, f"expected one cycle, got {report['cycle_count']}"
    cycle = report["cycles"][0]
    assert cycle["path"] == THREE_CYCLE_PATH, f"path={cycle['path']}"
    assert cycle["path_printed"] == THREE_CYCLE_PRINTED, f"printed={cycle['path_printed']}"
    assert cycle["length"] == 3, f"length={cycle['length']}"
    assert set(report["kahn_leftover"]) == {CLAIM_ALPHA, CLAIM_BETA, CLAIM_GAMMA}, (
        f"kahn_leftover={report['kahn_leftover']}"
    )
    assert report["graph_size"] == {"nodes": 3, "edges": 3, "contradiction_edges": 0}
    # The detector's path agrees with an independent walk of the planted edges.
    assert _walk_support(graph, CLAIM_ALPHA, 3) == cycle["path"], "walk disagrees"
    try:
        enforce(graph)
    except CyclicEvidenceError as exc:
        assert THREE_CYCLE_PRINTED in str(exc), f"enforce message {exc}"
    else:
        raise AssertionError("enforce accepted a cyclic support graph")
    return {
        "fired": True,
        "status": report["status"],
        "path": list(cycle["path"]),
        "path_printed": cycle["path_printed"],
        "length": cycle["length"],
        "kahn_leftover": sorted(report["kahn_leftover"]),
    }


def test_diamond_is_silent() -> dict[str, Any]:
    """The diamond (shared ancestor, no directed closed walk) is ACYCLIC with zero cycles."""
    graph = planted_diamond_long_chain()
    report = inspect(graph)
    assert report["status"] == STATUS_ACYCLIC, f"diamond status={report['status']}"
    assert report["cycles"] == [], f"diamond flagged cycles={report['cycles']}"
    assert report["cycle_count"] == 0
    assert report["kahn_leftover"] == [], f"diamond kahn_leftover={report['kahn_leftover']}"
    assert report["accepted"] is True, "an acyclic support graph is accepted"
    assert report["graph_size"] == {"nodes": 8, "edges": 8, "contradiction_edges": 0}
    # Both chains really do meet at the shared ancestor; that is what makes it a diamond.
    assert _walk_support(
        {"support_edges": graph["support_edges"][:4]}, CLAIM_TIP, 4
    )[-1] == EV_ROOT
    assert _walk_support(
        {"support_edges": graph["support_edges"][4:]}, CLAIM_TIP, 4
    )[-1] == EV_ROOT
    assert enforce(graph)["status"] == STATUS_ACYCLIC
    return {
        "fired": False,
        "status": report["status"],
        "cycles": [],
        "cycle_count": report["cycle_count"],
        "graph_size": dict(report["graph_size"]),
    }


def test_empty_graph_not_checked() -> dict[str, Any]:
    """Zero support edges is NOT-CHECKED (not ACYCLIC), never accepted, size still reported."""
    graph = planted_empty_evidence()
    report = inspect(graph)
    assert report["status"] == STATUS_NOT_CHECKED, f"empty status={report['status']}"
    assert report["accepted"] is False, "an unchecked graph must not be accepted"
    assert report["cycles"] == [] and report["cycle_count"] == 0
    assert report["graph_size"]["edges"] == 0, f"graph_size={report['graph_size']}"
    assert report["graph_size"]["nodes"] == 3, "zero-cycle vs empty must stay distinguishable"
    assert report["graph_size"]["contradiction_edges"] == 2
    assert len(report["contradiction_edges"]) == 2, "contradiction pair must be kept"
    # A support graph that is literally empty (no nodes either) is also NOT-CHECKED.
    bare = inspect({"nodes": [], "support_edges": []})
    assert bare["status"] == STATUS_NOT_CHECKED and bare["graph_size"]["nodes"] == 0
    try:
        enforce(graph)
    except EmptyEvidenceError:
        pass
    else:
        raise AssertionError("enforce accepted an empty support graph")
    return {
        "status": report["status"],
        "accepted": report["accepted"],
        "graph_size": dict(report["graph_size"]),
        "contradiction_edges": len(report["contradiction_edges"]),
    }


class EvidenceCycleTests(unittest.TestCase):
    def test_planted_three_node_cycle_fires(self) -> None:
        seen = test_planted_three_node_cycle_fires()
        self.assertEqual(seen["path_printed"], THREE_CYCLE_PRINTED)

    def test_diamond_is_silent(self) -> None:
        seen = test_diamond_is_silent()
        self.assertFalse(seen["fired"])

    def test_empty_graph_not_checked(self) -> None:
        seen = test_empty_graph_not_checked()
        self.assertEqual(seen["status"], STATUS_NOT_CHECKED)

    def test_both_states_differ(self) -> None:
        """The same detector fires on the loop and is silent on the diamond."""
        fired = inspect(planted_three_node_cycle())["status"]
        silent = inspect(planted_diamond_long_chain())["status"]
        self.assertNotEqual(fired, silent)
        self.assertEqual((fired, silent), (STATUS_CYCLIC, STATUS_ACYCLIC))


__all__ = [
    "THREE_CYCLE_PATH",
    "THREE_CYCLE_PRINTED",
    "planted_diamond_long_chain",
    "planted_empty_evidence",
    "planted_three_node_cycle",
    "test_diamond_is_silent",
    "test_empty_graph_not_checked",
    "test_planted_three_node_cycle_fires",
]


if __name__ == "__main__":
    unittest.main()
