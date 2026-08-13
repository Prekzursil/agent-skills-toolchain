"""Exact scheduling-integrity measurement for platform/architecture/distributed-runtime.md.

Answers, by algorithm rather than judgement:
  1. Where does every dependency edge resolve? (unit id / bucket id / nowhere)
  2. Can a bucket-level edge be expanded into unit-level edges from the catalog alone?
  3. What is the declared wall-clock budget, and the serial-vs-parallel span?
  4. How many units are declared parallel AND mutating on the shared checkout?

Read-only. Writes nothing. Emits a §4 terminal marker on stderr.
"""

from __future__ import annotations

import collections
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
CAT = ROOT / "command-center" / "WORK-UNIT-CATALOG.json"
PG = ROOT / "command-center" / "PHASE-GRAPH.json"

cat = json.loads(CAT.read_text(encoding="utf-8"))
pg = json.loads(PG.read_text(encoding="utf-8"))
units = cat["work_units"]

unit_ids = {u["id"] for u in units}
pg_buckets = {str(b["id"]): b for b in pg["allocation_buckets"]["buckets"]}
BUCKET_SHAPE = re.compile(r"^B[0-9]{2}$")

out: dict[str, object] = {"probe": __file__, "catalog_units": len(units)}

# ---- 1. edge resolution ------------------------------------------------------
res = collections.Counter()
bucket_edge_targets = collections.Counter()
invalid_tokens = collections.Counter()
for u in units:
    for dep in u.get("dependencies") or []:
        s = str(dep)
        if s in unit_ids:
            res["resolves_to_unit_id"] += 1
        elif s in pg_buckets:
            res["resolves_to_PHASE_GRAPH_bucket"] += 1
            bucket_edge_targets[s] += 1
        elif BUCKET_SHAPE.match(s):
            res["bucket_shaped_but_undeclared"] += 1
        else:
            res["resolves_NOWHERE"] += 1
            invalid_tokens[s] += 1
out["edge_resolution"] = dict(res)
out["total_edges"] = sum(res.values())
out["invalid_dep_tokens"] = dict(invalid_tokens)
out["units_carrying_an_invalid_dep"] = sum(
    1
    for u in units
    if any(
        str(d) not in unit_ids
        and str(d) not in pg_buckets
        and not BUCKET_SHAPE.match(str(d))
        for d in (u.get("dependencies") or [])
    )
)

# ---- 2. can a bucket edge be expanded? --------------------------------------
cat_bucket_members = collections.Counter(
    str(u["bucket"]) for u in units if u.get("bucket")
)
out["bucket_namespace"] = {
    "declared_in_PHASE_GRAPH": sorted(pg_buckets),
    "declared_count": len(pg_buckets),
    "declared_unit_totals": {k: v["units"] for k, v in sorted(pg_buckets.items())},
    "declared_unit_sum": sum(v["units"] for v in pg_buckets.values()),
    "assigned_in_CATALOG_bucket_field": dict(sorted(cat_bucket_members.items())),
    "catalog_units_with_no_bucket": sum(1 for u in units if not u.get("bucket")),
}
expandable = {t: cat_bucket_members.get(t, 0) for t in sorted(bucket_edge_targets)}
out["bucket_edges_by_target"] = dict(sorted(bucket_edge_targets.items()))
out["catalog_members_per_referenced_bucket"] = expandable
out["bucket_edges_expandable_to_unit_level"] = sum(
    n for t, n in bucket_edge_targets.items() if cat_bucket_members.get(t, 0) > 0
)
out["bucket_edges_NOT_expandable"] = sum(
    n for t, n in bucket_edge_targets.items() if cat_bucket_members.get(t, 0) == 0
)

# ---- 3. wall-clock span ------------------------------------------------------
to = {u["id"]: u["timeout_seconds"] for u in units}
serial_h = sum(to.values()) / 3600.0
by_phase: dict[str, list[int]] = collections.defaultdict(list)
for u in units:
    by_phase[str(u.get("phase"))].append(u["timeout_seconds"])


def span_hours(conc: int) -> float:
    """Phase-ordered span: phases run in the PHASE-GRAPH critical-path order,
    units inside a phase run at `conc` concurrency, each taking its full timeout.
    Upper bound on wall clock; a real run finishes sooner."""
    total = 0.0
    for phase, tos in by_phase.items():
        lanes = [0.0] * max(1, conc)
        for t in sorted(tos, reverse=True):
            i = lanes.index(min(lanes))
            lanes[i] += t
        total += max(lanes)
    return total / 3600.0


out["wall_clock"] = {
    "declared_timeout_sum_hours": round(serial_h, 1),
    "phase_serialized_span_hours": {
        str(c): round(span_hours(c), 1) for c in (1, 5, 10, 20, 50, 100)
    },
    "note": "worst case per unit (every unit burns its full timeout); phases serialized "
    "in PHASE-GRAPH order, units within a phase at the stated concurrency.",
}
out["critical_path_phases"] = pg["critical_path"]["path"]

# ---- 4. parallel + mutating on the shared checkout --------------------------
MUTATORS = ("Edit", "Write")


def mutates(u: dict) -> bool:
    perms = u.get("tool_permissions") or []
    return any(str(p).split("(")[0].strip() in MUTATORS for p in perms)


sub = collections.Counter(str(u.get("execution_substrate")) for u in units)
out["substrate"] = dict(sub)
out["shared_checkout_mutation_hazard"] = {
    "local_parallel_total": sub["local-parallel"],
    "local_parallel_AND_mutating": sum(
        1
        for u in units
        if u.get("execution_substrate") == "local-parallel" and mutates(u)
    ),
    "worktree_isolated_total": sub["worktree-isolated"],
    "definition": "substrate=local-parallel AND tool_permissions grants Edit or Write; "
    "these are declared to run concurrently against ONE working tree and git index.",
}

json.dump(out, sys.stdout, indent=1)
print()
print("SUCCESS:dr-scheduling-probe", file=sys.stderr)
