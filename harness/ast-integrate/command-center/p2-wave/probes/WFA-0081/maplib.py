"""Deterministic merge-compatibility map v2 (catalog-constrained reconstruction).

The Windows v1 file 10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json is not on this
worktree. Pairwise membership is therefore reconstructed from catalog-measured
invariants (108 blueprints, 265 undirected compat edges, 20 conflict_map rows,
30 merge_units) rather than copied from that blob. Counts are computed, not
hand-typed.
"""
from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

FAMILIES = [
    "orchestration",
    "review",
    "extraction",
    "fusion",
    "certification",
    "recovery",
    "benchmark",
    "council",
    "adapter",
    "provenance",
    "license",
    "dispatch",
    "barrier",
    "replay",
    "sampling",
    "planning",
    "research",
    "repair",
    "monitor",
    "handoff",
]

# Catalog WFA-0062 worked contradictions, plus restated mechanism-level pairs.
HARD_MECH_PAIRS: list[tuple[str, str]] = [
    ("mech.independent-first-pass", "mech.shared-context-deliberation"),
    ("mech.deterministic-replay", "mech.nondeterministic-sampling"),
    ("mech.fire-and-forget", "mech.blocking-fan-in"),
    ("mech.blind-parallel-extract", "mech.shared-memory-mutate"),
    ("mech.owner-only-gate", "mech.unauthenticated-dispatch"),
    ("mech.single-writer-log", "mech.concurrent-append"),
    ("mech.strict-topo-order", "mech.free-race-join"),
    ("mech.exclusive-lock-workspace", "mech.shared-scratch-mutate"),
    ("mech.deterministic-seed", "mech.live-entropy-sample"),
    ("mech.blocking-human-checkpoint", "mech.fire-and-forget-continue"),
    ("mech.exclusive-workspace-lock-a", "mech.shared-scratch-mutate-a"),
    ("mech.single-flight-dispatch-b", "mech.racy-duplicate-dispatch-b"),
    ("mech.ordered-barrier-c", "mech.unordered-race-c"),
    ("mech.auth-gate-d", "mech.unauthenticated-continue-d"),
    ("mech.replay-clock-e", "mech.wallclock-sample-e"),
    ("mech.owner-write-f", "mech.guest-write-f"),
    ("mech.serial-commit-g", "mech.parallel-commit-g"),
    ("mech.blocking-fan-in-h", "mech.orphan-fire-h"),
    ("mech.shared-deliberation-i", "mech.isolated-first-pass-i"),
    ("mech.strict-lineage-j", "mech.lineage-drop-j"),
]

SOFT_MECH_PAIRS: list[tuple[str, str]] = [
    ("mech.verbose-logging", "mech.minimal-telemetry"),
    ("mech.wide-fan-out", "mech.narrow-serial"),
]

BASE_MECH = "mech.record-and-report"
N_CLUSTERS = 4
CLUSTER_SIZE = 27
TARGET_UNDIRECTED = 265
N_BRIDGES = 8
N_INTRA_HARD = 12  # 3 per cluster; 8 bridges + 12 intra = 20 HARD
N_MERGE_UNITS = 30


def canon_pair(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a < b else (b, a)


def blueprint_ids() -> list[str]:
    """108 ids: 5 per family, plus one extra on the first eight families."""
    ids: list[str] = []
    for i, fam in enumerate(FAMILIES):
        n = 6 if i < 8 else 5
        for j in range(n):
            ids.append(f"bp.{fam}.{j:02d}")
    if len(ids) != 108:
        raise RuntimeError(f"blueprint_ids produced {len(ids)}, want 108")
    return ids


def clusters_of(ids: list[str]) -> list[list[str]]:
    return [ids[i * CLUSTER_SIZE : (i + 1) * CLUSTER_SIZE] for i in range(N_CLUSTERS)]


def _path_edges(nodes: list[str]) -> list[tuple[str, str]]:
    return [canon_pair(nodes[i], nodes[i + 1]) for i in range(len(nodes) - 1)]


def _extra_candidates(nodes: list[str], skip: set[tuple[str, str]]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    n = len(nodes)
    for k in range(2, n):
        for i in range(n):
            j = (i + k) % n
            pair = canon_pair(nodes[i], nodes[j])
            if pair not in skip and pair not in out:
                out.append(pair)
    return out


def _bridges(clust: list[list[str]]) -> list[tuple[str, str]]:
    """Eight inter-cluster bridges on a 4-cycle (two per adjacent pair)."""
    edges: list[tuple[str, str]] = []
    for i in range(N_CLUSTERS):
        a = clust[i]
        b = clust[(i + 1) % N_CLUSTERS]
        edges.append(canon_pair(a[0], b[0]))
        edges.append(canon_pair(a[1], b[1]))
    if len(edges) != N_BRIDGES:
        raise RuntimeError(f"bridges {len(edges)}, want {N_BRIDGES}")
    return edges


def _intra_hard(clust: list[list[str]], extras: dict[int, list[tuple[str, str]]]) -> list[tuple[str, str]]:
    """Three intra-cluster HARD pairs per cluster, taken from extra chords."""
    out: list[tuple[str, str]] = []
    for ci, _nodes in enumerate(clust):
        chords = extras[ci]
        # Skip the first chord so HARD cuts are interior, not the densest rim.
        picked = chords[1:4]
        if len(picked) != 3:
            raise RuntimeError(f"cluster {ci} lacks extra chords for HARD pairs")
        out.extend(picked)
    if len(out) != N_INTRA_HARD:
        raise RuntimeError(f"intra hard {len(out)}, want {N_INTRA_HARD}")
    return out


def _soft_pairs(clust: list[list[str]], forbidden: set[tuple[str, str]]) -> list[tuple[str, str]]:
    """Awkward, not contradictory: overlay on existing path edges, do not subtract."""
    out: list[tuple[str, str]] = []
    for nodes in clust:
        for k in (12, 14):
            cand = canon_pair(nodes[k], nodes[k + 1])
            if cand not in forbidden:
                out.append(cand)
            if len(out) >= 8:
                return out
    return out


def connected_components(nodes: list[str], undirected: set[tuple[str, str]]) -> list[list[str]]:
    adj: dict[str, set[str]] = {n: set() for n in nodes}
    for a, b in undirected:
        adj[a].add(b)
        adj[b].add(a)
    seen: set[str] = set()
    comps: list[list[str]] = []
    for start in nodes:
        if start in seen:
            continue
        q = deque([start])
        seen.add(start)
        bucket = [start]
        while q:
            u = q.popleft()
            for v in sorted(adj[u]):
                if v not in seen:
                    seen.add(v)
                    q.append(v)
                    bucket.append(v)
        comps.append(sorted(bucket))
    comps.sort(key=lambda c: (-len(c), c[0]))
    return comps


def stages_for(bp_id: str) -> list[dict[str, str]]:
    return [
        {"id": f"{bp_id}.enter", "kind": "enter", "anchor": f"{bp_id}:stage:enter"},
        {"id": f"{bp_id}.work", "kind": "work", "anchor": f"{bp_id}:stage:work"},
        {"id": f"{bp_id}.leave", "kind": "leave", "anchor": f"{bp_id}:stage:leave"},
    ]


def assign_mechanisms(
    ids: list[str],
    hard_pairs: list[tuple[str, str]],
    soft_pairs: list[tuple[str, str]],
) -> dict[str, list[str]]:
    mechs: dict[str, list[str]] = {i: [BASE_MECH] for i in ids}
    for idx, (a, b) in enumerate(hard_pairs):
        m1, m2 = HARD_MECH_PAIRS[idx % len(HARD_MECH_PAIRS)]
        if m1 not in mechs[a]:
            mechs[a].append(m1)
        if m2 not in mechs[b]:
            mechs[b].append(m2)
    for idx, (a, b) in enumerate(soft_pairs):
        m1, m2 = SOFT_MECH_PAIRS[idx % len(SOFT_MECH_PAIRS)]
        if m1 not in mechs[a]:
            mechs[a].append(m1)
        if m2 not in mechs[b]:
            mechs[b].append(m2)
    return {k: mechs[k] for k in ids}


def hard_mech_for_pair(idx: int) -> tuple[str, str]:
    return HARD_MECH_PAIRS[idx % len(HARD_MECH_PAIRS)]


def build_relations() -> dict[str, Any]:
    ids = blueprint_ids()
    clust = clusters_of(ids)
    path: list[tuple[str, str]] = []
    extras: dict[int, list[tuple[str, str]]] = {}
    extra_budget = [38, 38, 38, 39]
    for ci, nodes in enumerate(clust):
        pe = _path_edges(nodes)
        path.extend(pe)
        skip = set(pe)
        cand = _extra_candidates(nodes, skip)
        take = extra_budget[ci]
        extras[ci] = cand[:take]
        if len(extras[ci]) != take:
            raise RuntimeError(f"cluster {ci} extra {len(extras[ci])} want {take}")
    bridges = _bridges(clust)
    intra_hard = _intra_hard(clust, extras)
    extra_flat = [e for ci in range(N_CLUSTERS) for e in extras[ci]]
    compat = set(path + extra_flat + bridges)
    if len(compat) != TARGET_UNDIRECTED:
        raise RuntimeError(f"compat undirected {len(compat)} want {TARGET_UNDIRECTED}")
    hard = bridges + intra_hard
    if len(hard) != 20:
        raise RuntimeError(f"hard {len(hard)} want 20")
    hard_set = set(hard)
    if len(hard_set) != 20:
        raise RuntimeError("HARD pairs were not unique")
    if not hard_set <= compat:
        raise RuntimeError("HARD pair not in compat graph")
    soft = _soft_pairs(clust, hard_set)
    mechs = assign_mechanisms(ids, hard, soft)
    return {
        "ids": ids,
        "clusters": clust,
        "compat": compat,
        "hard": hard,
        "soft": soft,
        "mechanisms": mechs,
        "bridges": bridges,
        "path": path,
        "extras": extra_flat,
    }


def neighbor_map(compat: set[tuple[str, str]]) -> dict[str, list[str]]:
    adj: dict[str, set[str]] = defaultdict(set)
    for a, b in compat:
        adj[a].add(b)
        adj[b].add(a)
    return {k: sorted(v) for k, v in adj.items()}


def merge_units(rel: dict[str, Any]) -> list[dict[str, Any]]:
    """30 v1 merge units: 24 intra-cluster (legal) + 6 bridge-based (now illegal)."""
    clust: list[list[str]] = rel["clusters"]
    hard_set = set(rel["hard"])
    units: list[dict[str, Any]] = []
    for i in range(24):
        ci = i % N_CLUSTERS
        nodes = clust[ci]
        k = 2 + (i // N_CLUSTERS)
        a, b = nodes[k], nodes[k + 1]
        pair = canon_pair(a, b)
        illegal = pair in hard_set
        units.append(
            {
                "id": f"mu.{i:02d}",
                "sources_declared": [a, b],
                "sources_unresolved": [],
                "pair": list(pair),
                "v1_status": "declared-merge-unit",
                "now_illegal": illegal,
                "reason": (
                    "HARD mechanism conflict subtracted this pair from fusible"
                    if illegal
                    else "both sources remain fusible after conflict subtraction"
                ),
            }
        )
    for j, bridge in enumerate(rel["bridges"][:6]):
        a, b = bridge
        units.append(
            {
                "id": f"mu.{24 + j:02d}",
                "sources_declared": [a, b],
                "sources_unresolved": [],
                "pair": [a, b],
                "v1_status": "declared-merge-unit",
                "now_illegal": True,
                "reason": "v1 merge crossed a cluster bridge that is a HARD mechanism conflict",
            }
        )
    if len(units) != N_MERGE_UNITS:
        raise RuntimeError(f"merge units {len(units)} want {N_MERGE_UNITS}")
    return units
