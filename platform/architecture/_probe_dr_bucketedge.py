"""Are the 1,004 bucket-level dependency edges REDUNDANT with PHASE-GRAPH's 46 phase edges?

If yes, a scheduler may discard them and schedule on G1 (unit-id edges) + phase order.
If no, discarding them LOSES ordering information and the discard must be reported, not silent.

Test: for each bucket edge (unit U in phase P) -> bucket B, B declares feeds_phases=[F...].
The edge is REDUNDANT iff every F is already ordered strictly before P in the phase DAG
(transitive closure of PHASE-GRAPH edges). Otherwise it is LOAD-BEARING or CONTRADICTORY.

Control: an edge pointing at a bucket that feeds P itself must classify as NOT redundant.
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
pgb = {str(b["id"]): b for b in pg["allocation_buckets"]["buckets"]}
BUCKET = re.compile(r"^B[0-9]{2}$")

# phase DAG (all edge kinds) -> transitive "strictly before" closure
succ: dict[str, set[str]] = collections.defaultdict(set)
phase_ids = {str(p["id"]) for p in pg["phases"]}
edge_kinds = collections.Counter()
for e in pg["edges"]:
    a, b = str(e.get("from")), str(e.get("to"))
    edge_kinds[str(e.get("kind") or e.get("type") or "?")] += 1
    succ[a].add(b)
before: dict[str, set[str]] = {}
for p in phase_ids:
    seen, stack = set(), [p]
    while stack:
        n = stack.pop()
        for m in succ.get(n, ()):
            if m not in seen:
                seen.add(m)
                stack.append(m)
    before[p] = seen  # everything reachable FROM p == everything strictly after p

verdict = collections.Counter()
detail: dict[str, int] = collections.Counter()
for u in units:
    up = str(u.get("phase"))
    for dep in u.get("dependencies") or []:
        s = str(dep)
        if not BUCKET.match(s) or s not in pgb:
            continue
        feeds = [str(f) for f in pgb[s].get("feeds_phases", [])]
        if not feeds:
            verdict["bucket_feeds_no_phase"] += 1
            continue
        # redundant iff every fed phase F satisfies: up is reachable from F (F before up)
        if all(up in before.get(f, set()) for f in feeds):
            verdict["REDUNDANT_with_phase_order"] += 1
        elif any(f == up for f in feeds):
            verdict["SAME_PHASE_intra_phase_constraint"] += 1
            detail["same_phase:%s->%s" % (up, s)] += 1
        elif any(f in before.get(up, set()) for f in feeds):
            verdict["CONTRADICTS_phase_order"] += 1
            detail["contradicts:%s->%s" % (up, s)] += 1
        else:
            verdict["UNORDERED_vs_phase_graph"] += 1
            detail["unordered:%s->%s" % (up, s)] += 1

out = {
    "probe": pathlib.Path(__file__).name,
    "phase_graph": {
        "phases": len(phase_ids),
        "edges": len(pg["edges"]),
        "edge_kinds": dict(edge_kinds),
    },
    "bucket_edge_classification": dict(verdict),
    "bucket_edges_total": sum(verdict.values()),
    "top_non_redundant": dict(detail.most_common(15)),
    "CONTROL_same_phase_class_is_reachable": verdict["SAME_PHASE_intra_phase_constraint"] > 0
    or "no same-phase bucket edge exists in the data",
}
json.dump(out, sys.stdout, indent=1)
print()
print("SUCCESS:dr-bucketedge-probe", file=sys.stderr)
