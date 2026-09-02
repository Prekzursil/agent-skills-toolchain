#!/usr/bin/env python3
"""Probe 2: empty-evidence graph is NOT-CHECKED; Kahn agrees with DFS.

Mechanically different from probe 1:
  * Kahn leftover is computed HERE from the raw edge list, not by reading
    evidence_graph.kahn_leftover.
  * An undirected cycle walk flags the diamond (the four-cycles through the
    shared ancestor). The directed detector must stay silent — that is the
    control that a diamond-flagging mutant is unusable.
  * Zero support edges must not be reported as ACYCLIC.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(HERE))

from council.evidence_graph import inspect  # noqa: E402
from council.tests.test_evidence_cycles import (  # noqa: E402
    test_empty_graph_not_checked,
)
from fixtures import (  # noqa: E402
    CLAIM_ALPHA,
    CLAIM_BETA,
    CLAIM_GAMMA,
    planted_diamond_long_chain,
    planted_empty_evidence,
    planted_three_node_cycle,
)

UNIT = "TST-0261"
ART = REPO / "command-center" / "receipts" / "TST-0261.json"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})
SENTINEL = "SUCCESS:TST-0261"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0261-probe2 {msg}")
    return 1


def independent_kahn_leftover(edges: list[tuple[str, str]]) -> list[str]:
    """Kahn residual. Copied into the probe so a stub library cannot hide a cycle."""
    adj: dict[str, set[str]] = defaultdict(set)
    indeg: dict[str, int] = defaultdict(int)
    nodes: set[str] = set()
    for src, dst in edges:
        if not src or not dst:
            continue
        if dst in adj[src]:
            continue
        adj[src].add(dst)
        indeg[dst] += 1
        nodes.add(src)
        nodes.add(dst)
        indeg.setdefault(src, indeg[src])
    queue = [n for n in sorted(nodes) if indeg[n] == 0]
    while queue:
        n = queue.pop(0)
        for nxt in sorted(adj[n]):
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                queue.append(nxt)
    return sorted(n for n in nodes if indeg[n] > 0)


def undirected_has_cycle(edges: list[tuple[str, str]]) -> bool:
    """Treat support edges as undirected. A diamond has an undirected cycle."""
    adj: dict[str, set[str]] = defaultdict(set)
    for src, dst in edges:
        if not src or not dst or src == dst:
            continue
        adj[src].add(dst)
        adj[dst].add(src)
    seen: set[str] = set()

    def dfs(node: str, parent: str | None) -> bool:
        seen.add(node)
        for nxt in adj[node]:
            if nxt == parent:
                continue
            if nxt in seen:
                return True
            if dfs(nxt, node):
                return True
        return False

    for n in sorted(adj):
        if n not in seen and dfs(n, None):
            return True
    return False


def edge_tuples(graph: dict) -> list[tuple[str, str]]:
    return [(e["from"], e["to"]) for e in graph.get("support_edges") or []]


def check_receipt() -> dict:
    if not ART.is_file():
        return {"present": False, "ok": True, "skipped": True}
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        return {"present": True, "ok": False, "reason": f"self-declared:{st}"}
    if SENTINEL not in text:
        return {"present": True, "ok": False, "reason": "sentinel-absent"}
    empty = doc.get("empty_evidence_graph") or {}
    if empty.get("status") != "NOT-CHECKED":
        return {
            "present": True,
            "ok": False,
            "reason": f"receipt empty status={empty.get('status')}",
        }
    size = empty.get("graph_size") or {}
    if size.get("edges") != 0:
        return {"present": True, "ok": False, "reason": f"receipt empty edges={size}"}
    if empty.get("accepted") is True:
        return {"present": True, "ok": False, "reason": "receipt accepted empty graph"}
    if "graph_size" not in doc and not size:
        return {"present": True, "ok": False, "reason": "receipt missing graph_size"}
    return {"present": True, "ok": True, "skipped": False, "state": st}


def main() -> int:
    try:
        empty_test = test_empty_graph_not_checked()
    except AssertionError as exc:
        return fail(str(exc))

    three = planted_three_node_cycle()
    diamond = planted_diamond_long_chain()
    empty = planted_empty_evidence()

    three_edges = edge_tuples(three)
    diamond_edges = edge_tuples(diamond)
    empty_edges = edge_tuples(empty)

    three_leftover = set(independent_kahn_leftover(three_edges))
    if three_leftover != {CLAIM_ALPHA, CLAIM_BETA, CLAIM_GAMMA}:
        return fail(f"independent Kahn missed 3-cycle leftover={three_leftover}")
    diamond_leftover = independent_kahn_leftover(diamond_edges)
    if diamond_leftover:
        return fail(f"independent Kahn flagged diamond leftover={diamond_leftover}")
    empty_leftover = independent_kahn_leftover(empty_edges)
    if empty_leftover:
        return fail(f"independent Kahn leftover on zero edges {empty_leftover}")

    lib_three = inspect(three)
    lib_diamond = inspect(diamond)
    lib_empty = inspect(empty)

    if set(lib_three.get("kahn_leftover") or []) != three_leftover:
        return fail("library Kahn disagrees with probe Kahn on 3-cycle")
    if lib_three["status"] != "CYCLIC":
        return fail("library silent on 3-cycle under probe2")
    if lib_diamond["status"] != "ACYCLIC":
        return fail(f"library diamond {lib_diamond['status']}")
    if lib_empty["status"] != "NOT-CHECKED":
        return fail(f"library empty {lib_empty['status']}")

    if not undirected_has_cycle(diamond_edges):
        return fail("undirected mutant control did not see the diamond")
    if undirected_has_cycle(diamond_edges) and lib_diamond["cycles"]:
        return fail("directed detector copied the undirected diamond-flagging mutant")
    if not undirected_has_cycle(three_edges):
        return fail("undirected walk missed the 3-cycle (control is inert)")
    if undirected_has_cycle(empty_edges):
        return fail("undirected walk fired on zero support edges")

    if lib_empty["graph_size"]["edges"] != 0:
        return fail("empty graph_size.edges is not 0")
    if lib_empty["graph_size"]["nodes"] < 3:
        return fail("empty graph_size.nodes collapsed; zero-cycle vs empty indistinguishable")
    if lib_empty.get("accepted") is True:
        return fail("empty graph accepted")
    if lib_empty["contradiction_edges"] and lib_empty["cycles"]:
        return fail("contradiction 2-cycle reported as circular citation")

    receipt = check_receipt()
    if receipt.get("ok") is not True:
        return fail(f"receipt {receipt}")

    payload = {
        "probe": "probe2-empty-and-kahn",
        "unit_id": UNIT,
        "test_empty_graph_not_checked": empty_test,
        "independent_kahn": {
            "three_cycle_leftover": sorted(three_leftover),
            "diamond_leftover": diamond_leftover,
            "empty_leftover": empty_leftover,
        },
        "undirected_mutant": {
            "diamond_undirected_cycle": True,
            "three_undirected_cycle": True,
            "empty_undirected_cycle": False,
            "directed_diamond_silent": True,
        },
        "library": {
            "three_status": lib_three["status"],
            "diamond_status": lib_diamond["status"],
            "empty_status": lib_empty["status"],
            "empty_graph_size": lib_empty["graph_size"],
            "three_graph_size": lib_three["graph_size"],
            "diamond_graph_size": lib_diamond["graph_size"],
        },
        "receipt": receipt,
        "pass": True,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(
        "SUCCESS:TST-0261-probe2 empty-evidence NOT-CHECKED; "
        "Kahn leftover on 3-cycle; diamond undirected-cycle but directed-silent"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
