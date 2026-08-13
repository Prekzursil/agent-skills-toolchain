"""Is the 2,007-unit dependency graph schedulable? Exact algorithm, not judgement.

Three graphs are tested, because the answer differs and the difference is the finding:
  G1 unit-id edges only            (2,644 edges, ignore bucket edges)
  G2 + bucket edges expanded via CATALOG `bucket` field membership
  G3 + bucket edges expanded via PHASE-GRAPH bucket.feeds_phases -> catalog `phase`
     (the join this architecture proposes)

For each: acyclic? longest chain? width of the ready frontier at t0?
Includes a KNOWN-BROKEN control: an injected 3-cycle must be detected in every graph.
"""
from __future__ import annotations

import collections
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
cat = json.loads((ROOT / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
pg = json.loads((ROOT / "command-center" / "PHASE-GRAPH.json").read_text(encoding="utf-8"))
units = cat["work_units"]
by_id = {u["id"]: u for u in units}
pg_buckets = {str(b["id"]): b for b in pg["allocation_buckets"]["buckets"]}
BUCKET = re.compile(r"^B[0-9]{2}$")

phase_members: dict[str, list[str]] = collections.defaultdict(list)
for u in units:
    phase_members[str(u.get("phase"))].append(u["id"])
cat_bucket_members: dict[str, list[str]] = collections.defaultdict(list)
for u in units:
    if u.get("bucket"):
        cat_bucket_members[str(u["bucket"])].append(u["id"])


def build(mode: str) -> dict[str, set[str]]:
    """blocked_by adjacency: node -> set of nodes it waits on."""
    g: dict[str, set[str]] = {u["id"]: set() for u in units}
    for u in units:
        for dep in u.get("dependencies") or []:
            s = str(dep)
            if s in by_id:
                g[u["id"]].add(s)
            elif BUCKET.match(s) and mode != "unit-only":
                if mode == "catalog-bucket":
                    members = cat_bucket_members.get(s, [])
                else:  # phase-join
                    members = [
                        m
                        for ph in pg_buckets.get(s, {}).get("feeds_phases", [])
                        for m in phase_members.get(str(ph), [])
                    ]
                g[u["id"]].update(m for m in members if m != u["id"])
    return g


def analyse(g: dict[str, set[str]]) -> dict[str, object]:
    indeg = {n: len(d) for n, d in g.items()}
    blocks: dict[str, list[str]] = collections.defaultdict(list)
    for n, deps in g.items():
        for d in deps:
            blocks[d].append(n)
    ready0 = [n for n, k in indeg.items() if k == 0]
    q = collections.deque(sorted(ready0))
    depth = {n: 0 for n in ready0}
    order: list[str] = []
    rem = dict(indeg)
    while q:
        n = q.popleft()
        order.append(n)
        for m in blocks.get(n, []):
            rem[m] -= 1
            depth[m] = max(depth.get(m, 0), depth[n] + 1)
            if rem[m] == 0:
                q.append(m)
    acyclic = len(order) == len(g)
    return {
        "nodes": len(g),
        "edges": sum(len(d) for d in g.values()),
        "acyclic": acyclic,
        "topologically_ordered": len(order),
        "in_a_cycle_or_downstream_of_one": len(g) - len(order),
        "ready_frontier_at_t0": len(ready0),
        "longest_chain_levels": (max(depth.values()) + 1) if depth and acyclic else None,
    }


out: dict[str, object] = {"probe": pathlib.Path(__file__).name}
for mode, label in [
    ("unit-only", "G1_unit_id_edges_only"),
    ("catalog-bucket", "G2_bucket_via_catalog_bucket_field"),
    ("phase-join", "G3_bucket_via_PHASE_GRAPH_feeds_phases_join"),
]:
    out[label] = analyse(build(mode))

# KNOWN-BROKEN control: inject a 3-cycle; every graph must report it.
ctl = build("unit-only")
a, b, c = sorted(ctl)[:3]
ctl[a].add(b)
ctl[b].add(c)
ctl[c].add(a)
res = analyse(ctl)
out["CONTROL_injected_3cycle"] = {
    "nodes_forced_into_cycle": [a, b, c],
    "acyclic_reported": res["acyclic"],
    "detector_fires_on_known_broken": res["acyclic"] is False,
    "unordered_count": res["in_a_cycle_or_downstream_of_one"],
}

json.dump(out, sys.stdout, indent=1)
print()
ok = out["CONTROL_injected_3cycle"]["detector_fires_on_known_broken"]
print(
    ("SUCCESS" if ok else "FAILED") + ":dr-acyclic-probe"
    + ("" if ok else " control did not fire - detector is vacuous"),
    file=sys.stderr,
)
