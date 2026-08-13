"""Measure the distributed-runtime-relevant surface of WORK-UNIT-CATALOG.json.

Ground truth for platform/architecture/distributed-runtime.md. Read-only.
"""
import json
import collections
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
CAT = ROOT / "command-center" / "WORK-UNIT-CATALOG.json"

d = json.loads(CAT.read_text(encoding="utf-8"))
wu = d["work_units"]
out = {}
out["work_units"] = len(wu)
out["items_separate"] = len(d.get("items", []))

def dist(field):
    c = collections.Counter()
    for u in wu:
        v = u.get(field)
        if isinstance(v, list):
            c["<list len %d>" % len(v)] += 1
        elif isinstance(v, dict):
            c["<dict>"] += 1
        else:
            c[str(v)] += 1
    return dict(c.most_common())

out["execution_substrate"] = dist("execution_substrate")
out["phase"] = dist("phase")
out["bucket_count"] = len({u.get("bucket") for u in wu})
out["retry_policy_distinct"] = len({u.get("retry_policy") for u in wu})

# timeouts
to = [u.get("timeout_seconds") for u in wu if isinstance(u.get("timeout_seconds"), (int, float))]
to_s = sorted(to)
out["timeout_seconds"] = {
    "n": len(to),
    "missing_or_nonnumeric": len(wu) - len(to),
    "min": to_s[0] if to_s else None,
    "p50": to_s[len(to_s) // 2] if to_s else None,
    "p90": to_s[int(len(to_s) * 0.9)] if to_s else None,
    "max": to_s[-1] if to_s else None,
    "sum_hours": round(sum(to) / 3600.0, 1) if to else None,
    "distinct": len(set(to)),
}

# tool permissions
tp = collections.Counter()
tp_per_unit = []
for u in wu:
    v = u.get("tool_permissions")
    if isinstance(v, list):
        tp_per_unit.append(len(v))
        for x in v:
            tp[str(x)] += 1
    elif isinstance(v, str):
        tp_per_unit.append(1)
        tp[v] += 1
out["tool_permissions_top20"] = dict(tp.most_common(20))
out["tool_permissions_distinct"] = len(tp)
out["tool_permissions_per_unit_max"] = max(tp_per_unit) if tp_per_unit else None

# dependency graph shape
ids = {u["id"] for u in wu}
buckets = {u.get("bucket") for u in wu}
dep_kind = collections.Counter()
edges_unit = 0
edges_bucket = 0
edges_dangling = 0
indeg = collections.Counter()
for u in wu:
    deps = u.get("dependencies") or []
    if isinstance(deps, str):
        deps = [deps]
    for dep in deps:
        s = str(dep)
        if s in ids:
            dep_kind["unit-id"] += 1
            edges_unit += 1
            indeg[s] += 1
        elif s in buckets:
            dep_kind["bucket-id"] += 1
            edges_bucket += 1
        else:
            dep_kind["UNRESOLVABLE"] += 1
            edges_dangling += 1
out["dependency_edge_kinds"] = dict(dep_kind)
out["units_with_zero_deps"] = sum(1 for u in wu if not (u.get("dependencies") or []))

# output_schema surface
osc = collections.Counter()
for u in wu:
    v = u.get("output_schema")
    if v:
        osc[str(v).split("#")[0]] += 1
out["distinct_output_schema_files"] = len(osc)
out["total_output_schema_refs"] = sum(osc.values())
out["output_schema_top5"] = dict(osc.most_common(5))

# output_path collisions -> write contention
opc = collections.Counter(str(u.get("output_path")) for u in wu)
out["distinct_output_paths"] = len(opc)
out["colliding_output_paths"] = {k: v for k, v in opc.items() if v > 1}
out["output_path_top_dirs"] = dict(
    collections.Counter(
        str(u.get("output_path")).rsplit("/", 1)[0] for u in wu
    ).most_common(12)
)

# vendor / model split
vm = collections.Counter()
for u in wu:
    a = u.get("assigned_model_vendor_role") or {}
    if isinstance(a, dict):
        vm["%s/%s" % (a.get("vendor"), a.get("model"))] += 1
    else:
        vm["<non-dict:%s>" % type(a).__name__] += 1
out["vendor_model"] = dict(vm.most_common())

# owner approval + worktree
out["owner_approval_required_true"] = sum(1 for u in wu if u.get("owner_approval_required") is True)

print(json.dumps(out, indent=1, sort_keys=False))
print("SUCCESS:dr-catalog-probe", file=sys.stderr)
