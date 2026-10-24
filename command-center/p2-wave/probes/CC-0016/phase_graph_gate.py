#!/usr/bin/env python3
"""Extended parity/regeneration gate for command-center/PHASE-GRAPH.json (CC-0016).

command-center/DEPENDENCY-GRAPH.json is a FULLY MACHINE-DERIVED artifact
(103 work-unit nodes) produced byte-for-byte by ``tools/command-center/catalog.py:
build_graph``, and ``tools/command-center/validate.py`` (check V-GRAPH) asserts the
committed file equals ``build_graph(catalog)`` by whole-dict equality. That gate
runs in CI (.github/workflows/quality.yml).

PHASE-GRAPH.json is a DIFFERENT KIND OF ARTIFACT. Per its own
``relationship_to_dependency_graph_json`` block, it is a separate, additive
sidecar: 21 phase nodes, 46 edges, EACH AUTHORED FROM SPEC PROSE BY A SINGLE
AGENT with a hand-written ``reason`` string. There is no ``build_phase_graph()``
generator function anywhere in this repo, and the cited source prose
(``C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md``) does
not exist on this machine (measured: ``find / -iname _USER-PROMPTS.md`` -> zero
hits). So unlike DEPENDENCY-GRAPH.json, PHASE-GRAPH.json cannot be re-derived
byte-for-byte from an external source in this environment -- unauthored
"regeneration" of the AUTHORED edges/phases/reasons is not a real question this
gate can answer, and pretending otherwise would misrepresent hand-authored
provenance as a machine-derived fact (exactly what the catalog's own
``evidence_requirement`` for CC-0016 warns against).

What IS mechanically checkable, and what this gate checks, is INTERNAL
CONSISTENCY: whether the four DERIVED summary fields the sidecar itself carries
(``edge_count``, ``hard_edge_count``, ``soft_edge_count``, ``critical_path``)
are still a correct function of the AUTHORED ``phases``/``edges`` arrays.
"Regeneration" in this module therefore means: recompute those four derived
fields purely from ``phases``/``edges`` and compare against the recorded values.
A silent gate on the unmodified committed file demonstrates the derived fields
have not drifted from their authored source; a loud gate after any edge is
altered demonstrates the sidecar is not merely decorative JSON that nothing
actually checks.

Checks, each independently falsifiable:

  V-PHASEGRAPH-REF     referential integrity - every edge endpoint names a real
                        phase id.
  V-PHASEGRAPH-CYCLE    acyclicity - the full edge set (HARD+SOFT, both directed
                        precedence constraints) contains no cycle.
  V-PHASEGRAPH-COUNT     edge_count / hard_edge_count / soft_edge_count in the
                        file equal counts recomputed from the edges[] array.
  V-PHASEGRAPH-CRITPATH  critical_path.path is a real HARD-only chain in the
                        graph, critical_path.node_count equals len(path), and
                        that length equals the longest HARD-only chain
                        computed independently (Kahn topo-sort + DP longest
                        path over the 21-node DAG).

FAIL CLOSED: a missing file, unparseable JSON, or a HARD-edge cycle (which
would make the critical-path method itself ill-defined) is a failure, never
"nothing found -> pass".
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import deque
from pathlib import Path
from typing import Any

GATE_ID = "command-center/p2-wave/probes/CC-0016/phase_graph_gate.py@v1"
DEFAULT_GRAPH = "command-center/PHASE-GRAPH.json"


class Violation(dict):
    def __init__(self, check: str, item_id: str, detail: str) -> None:
        super().__init__(check=check, id=item_id, detail=detail)

    def __str__(self) -> str:  # pragma: no cover - trivial formatting
        return f"{self['check']} {self['id']}: {self['detail']}"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def node_ids(data: dict[str, Any]) -> list[str]:
    return [str(p.get("id")) for p in data.get("phases", []) if isinstance(p, dict)]


def detect_cycle(nodes: list[str], edges: list[tuple[str, str]]) -> tuple[bool, list[str]]:
    """Iterative DFS cycle detector. Returns (acyclic, cycle_path_if_any)."""
    adj: dict[str, list[str]] = {n: [] for n in nodes}
    for u, v in edges:
        if u in adj and v in adj:
            adj[u].append(v)
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {n: WHITE for n in nodes}
    for start in nodes:
        if color[start] != WHITE:
            continue
        stack: list[tuple[str, int]] = [(start, 0)]
        path: list[str] = [start]
        color[start] = GRAY
        while stack:
            node, idx = stack[-1]
            children = adj[node]
            if idx < len(children):
                stack[-1] = (node, idx + 1)
                nxt = children[idx]
                if color[nxt] == GRAY:
                    cyc_start = path.index(nxt)
                    return False, path[cyc_start:] + [nxt]
                if color[nxt] == WHITE:
                    color[nxt] = GRAY
                    stack.append((nxt, 0))
                    path.append(nxt)
            else:
                stack.pop()
                path.pop()
                color[node] = BLACK
    return True, []


def longest_hard_chain(
    nodes: list[str], edges: list[dict[str, Any]]
) -> tuple[list[str], bool]:
    """Longest chain (by node count) using HARD edges only. Kahn topo + DP.

    Returns (path, hard_subgraph_is_dag). If the HARD-only subgraph itself has
    a cycle, the critical-path method (defined over a DAG) is not well-formed
    and path is [].
    """
    hard = [(e.get("from"), e.get("to")) for e in edges if e.get("type") == "HARD"]
    adj: dict[str, list[str]] = {n: [] for n in nodes}
    indeg = {n: 0 for n in nodes}
    for u, v in hard:
        if u in adj and v in adj:
            adj[u].append(v)
            indeg[v] += 1
    q = deque(n for n in nodes if indeg[n] == 0)
    indeg_work = dict(indeg)
    topo: list[str] = []
    while q:
        u = q.popleft()
        topo.append(u)
        for v in adj[u]:
            indeg_work[v] -= 1
            if indeg_work[v] == 0:
                q.append(v)
    if len(topo) != len(nodes):
        return [], False  # cycle among HARD edges

    dist = {n: 1 for n in nodes}
    prev: dict[str, str | None] = {n: None for n in nodes}
    for u in topo:
        for v in adj[u]:
            if dist[u] + 1 > dist[v]:
                dist[v] = dist[u] + 1
                prev[v] = u
    end = max(nodes, key=lambda n: dist[n])
    chain = []
    cur: str | None = end
    while cur is not None:
        chain.append(cur)
        cur = prev[cur]
    chain.reverse()
    return chain, True


def compute(data: dict[str, Any]) -> dict[str, Any]:
    nodes = node_ids(data)
    edges = [e for e in data.get("edges", []) if isinstance(e, dict)]
    all_pairs = [(str(e.get("from")), str(e.get("to"))) for e in edges]
    acyclic, cycle_path = detect_cycle(nodes, all_pairs)
    hard_chain, hard_is_dag = longest_hard_chain(nodes, edges)
    return {
        "node_ids": nodes,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "hard_edge_count": sum(1 for e in edges if e.get("type") == "HARD"),
        "soft_edge_count": sum(1 for e in edges if e.get("type") == "SOFT"),
        "acyclic": acyclic,
        "cycle_path": cycle_path,
        "hard_subgraph_is_dag": hard_is_dag,
        "computed_critical_path": hard_chain,
        "computed_critical_path_len": len(hard_chain),
    }


def verify(data: dict[str, Any], computed: dict[str, Any]) -> list[Violation]:
    violations: list[Violation] = []
    nodes = set(computed["node_ids"])
    edges = [e for e in data.get("edges", []) if isinstance(e, dict)]

    # V-PHASEGRAPH-REF
    for e in edges:
        frm, to = str(e.get("from")), str(e.get("to"))
        if frm not in nodes:
            violations.append(
                Violation("V-PHASEGRAPH-REF", frm, f"edge from-endpoint {frm!r} is not a phase id")
            )
        if to not in nodes:
            violations.append(
                Violation("V-PHASEGRAPH-REF", to, f"edge to-endpoint {to!r} is not a phase id")
            )

    # V-PHASEGRAPH-CYCLE
    if not computed["acyclic"]:
        violations.append(
            Violation(
                "V-PHASEGRAPH-CYCLE",
                "-",
                f"phase graph contains a cycle: {' -> '.join(computed['cycle_path'])}",
            )
        )
    if not computed["hard_subgraph_is_dag"]:
        violations.append(
            Violation(
                "V-PHASEGRAPH-CYCLE",
                "-",
                "HARD-only subgraph contains a cycle; critical_path method is ill-defined",
            )
        )

    # V-PHASEGRAPH-COUNT
    recorded_edge_count = data.get("edge_count")
    recorded_hard = data.get("hard_edge_count")
    recorded_soft = data.get("soft_edge_count")
    if recorded_edge_count != computed["edge_count"]:
        violations.append(
            Violation(
                "V-PHASEGRAPH-COUNT",
                "-",
                f"edge_count field={recorded_edge_count!r} != recomputed len(edges)={computed['edge_count']}",
            )
        )
    if recorded_hard != computed["hard_edge_count"]:
        violations.append(
            Violation(
                "V-PHASEGRAPH-COUNT",
                "-",
                f"hard_edge_count field={recorded_hard!r} != recomputed={computed['hard_edge_count']}",
            )
        )
    if recorded_soft != computed["soft_edge_count"]:
        violations.append(
            Violation(
                "V-PHASEGRAPH-COUNT",
                "-",
                f"soft_edge_count field={recorded_soft!r} != recomputed={computed['soft_edge_count']}",
            )
        )

    # V-PHASEGRAPH-CRITPATH
    cp = data.get("critical_path", {}) if isinstance(data.get("critical_path"), dict) else {}
    recorded_path = cp.get("path") if isinstance(cp.get("path"), list) else None
    recorded_node_count = cp.get("node_count")
    if recorded_path is None:
        violations.append(
            Violation("V-PHASEGRAPH-CRITPATH", "-", "critical_path.path missing or not a list")
        )
    else:
        # Every consecutive pair in the recorded path must be a real HARD edge.
        hard_pairs = {
            (str(e.get("from")), str(e.get("to")))
            for e in edges
            if e.get("type") == "HARD"
        }
        for a, b in zip(recorded_path, recorded_path[1:]):
            if (a, b) not in hard_pairs:
                violations.append(
                    Violation(
                        "V-PHASEGRAPH-CRITPATH",
                        f"{a}->{b}",
                        "recorded critical_path.path step is not a HARD edge in edges[]",
                    )
                )
        if recorded_node_count != len(recorded_path):
            violations.append(
                Violation(
                    "V-PHASEGRAPH-CRITPATH",
                    "-",
                    f"critical_path.node_count={recorded_node_count!r} != len(path)={len(recorded_path)}",
                )
            )
        if computed["hard_subgraph_is_dag"] and len(recorded_path) != computed[
            "computed_critical_path_len"
        ]:
            violations.append(
                Violation(
                    "V-PHASEGRAPH-CRITPATH",
                    "-",
                    "recorded critical_path length="
                    f"{len(recorded_path)} != independently-recomputed longest "
                    f"HARD-only chain length={computed['computed_critical_path_len']}",
                )
            )

    return violations


def run(path: Path) -> tuple[list[Violation], dict[str, Any]]:
    try:
        data = load(path)
    except (OSError, json.JSONDecodeError) as exc:
        return [Violation("V-PHASEGRAPH-READ", "-", f"cannot read/parse {path}: {exc}")], {}
    computed = compute(data)
    violations = verify(data, computed)
    return violations, computed


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--graph", default=DEFAULT_GRAPH)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    path = Path(args.graph)
    violations, computed = run(path)

    if args.json:
        sentinel = (
            f"FAILED:phase-graph-gate violations={len(violations)}"
            if violations
            else (
                "SUCCESS:phase-graph-gate "
                f"nodes={computed.get('node_count')} edges={computed.get('edge_count')} "
                "derived-fields-match-authored-edges"
            )
        )
        print(
            json.dumps(
                {"violations": violations, "computed": computed, "sentinel": sentinel},
                indent=2,
                sort_keys=True,
            )
        )
        return 1 if violations else 0

    for v in violations:
        print(f"  {v}")
    if computed:
        print(
            "phase-graph-gate "
            f"nodes={computed['node_count']} edges={computed['edge_count']} "
            f"hard={computed['hard_edge_count']} soft={computed['soft_edge_count']} "
            f"acyclic={computed['acyclic']} "
            f"critical_path_len={computed['computed_critical_path_len']}"
        )
    if violations:
        print(f"FAILED:phase-graph-gate violations={len(violations)}")
        return 1
    print(
        "SUCCESS:phase-graph-gate "
        f"nodes={computed.get('node_count')} edges={computed.get('edge_count')} "
        "derived-fields-match-authored-edges"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
