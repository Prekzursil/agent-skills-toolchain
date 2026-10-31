"""Reconcile my re-derived numbers against the brief's numbers. State the DEFINITION
behind each, because a disagreement here is usually definitional, not factual."""
import json
import os
import re
import sys

REPO = r"C:\Users\Prekzursil\source\ast-integrate"
sys.path.insert(0, os.path.join(REPO, "platform", "lib"))
from receipt_schema_gate import parse_schema_ref  # noqa: E402

cat = json.load(open(os.path.join(REPO, "command-center", "WORK-UNIT-CATALOG.json"), encoding="utf-8"))
wus = cat["work_units"]
ids = {u["id"] for u in wus}
out = {}

# ---- A. is there a bucket registry outside the catalog? -------------------
pg = json.load(open(os.path.join(REPO, "command-center", "PHASE-GRAPH.json"), encoding="utf-8"))
ab = pg.get("allocation_buckets")
if isinstance(ab, dict):
    bnames = sorted(ab.keys())
elif isinstance(ab, list):
    bnames = sorted({(b.get("id") or b.get("bucket") or str(b)) if isinstance(b, dict) else str(b)
                     for b in ab})
else:
    bnames = []
out["phase_graph_allocation_bucket_names"] = bnames
out["phase_graph_bucket_count"] = len(bnames)
dg = json.load(open(os.path.join(REPO, "command-center", "DEPENDENCY-GRAPH.json"), encoding="utf-8"))
dnodes = dg.get("nodes")
dnames = sorted(n.get("id") if isinstance(n, dict) else str(n) for n in dnodes) if isinstance(dnodes, list) else []
out["dependency_graph_node_count"] = len(dnames)
out["dependency_graph_node_sample"] = dnames[:20]

known = set(bnames) | set(dnames) | ids
tokens = {}
for u in wus:
    d = u.get("dependencies")
    for t in (d if isinstance(d, list) else [d] if isinstance(d, str) else []):
        tokens[str(t).strip()] = tokens.get(str(t).strip(), 0) + 1
unres = {t: n for t, n in tokens.items() if t and t not in known}
out["dep_tokens_distinct"] = len(tokens)
out["dep_tokens_unresolved_against_catalog_PLUS_phasegraph_PLUS_depgraph"] = len(unres)
out["dep_tokens_unresolved_detail"] = dict(sorted(unres.items(), key=lambda kv: -kv[1])[:20])
out["dep_units_affected_by_unresolved"] = len([
    u for u in wus
    if any(str(t).strip() in unres for t in (u.get("dependencies") or []))
])

# ---- B. the 21-unit gap between 180 (non-bare) and 159 (text dropped) ----
BARE = re.compile(r"^[A-Za-z0-9_.\-/]+\.json(#/[A-Za-z0-9_.\-/$]*)?$")
gap = []
for u in wus:
    v = u.get("output_schema")
    if not isinstance(v, str):
        gap.append({"id": u["id"], "raw": repr(v), "why": "not a string"})
        continue
    head, frag = parse_schema_ref(v)
    kept = head + (frag or "")
    dropped = v[len(kept):].strip() if v.startswith(kept) else "<prefix-mismatch>"
    if not BARE.match(v.strip()) and not dropped:
        gap.append({"id": u["id"], "raw": v, "why": "non-bare but nothing dropped"})
out["gap_nonbare_but_nothing_dropped"] = len(gap)
out["gap_sample"] = gap[:8]

# ---- C. sentinel: strict two-position rule ------------------------------
loose = 0
strict = 0
no_failed = 0
for u in wus:
    s = u.get("completion_sentinel") or ""
    uid = u["id"]
    if uid not in s:
        loose += 1
    has_succ = f"SUCCESS:{uid}" in s
    has_fail = f"FAILED:{uid}" in s
    if not (has_succ and has_fail):
        strict += 1
    if "FAILED" not in s:
        no_failed += 1
out["sentinel_loose_missing_own_id"] = loose
out["sentinel_strict_missing_SUCCESS_or_FAILED_with_own_id"] = strict
out["sentinel_no_FAILED_branch_at_all"] = no_failed

# ---- D. role shape: the brief's definition vs mine ---------------------
n_str = sum(1 for u in wus if isinstance(u.get("assigned_model_vendor_role"), str))
n_dict_extra = sum(1 for u in wus
                   if isinstance(u.get("assigned_model_vendor_role"), dict)
                   and set(u["assigned_model_vendor_role"]) != {"model", "vendor", "role"})
out["role_bare_string_count"] = n_str
out["role_dict_with_extra_keys"] = n_dict_extra
out["role_strict_noncanonical_total"] = n_str + n_dict_extra

# ---- E. how big is the "config" the owner would have to read? ----------
sizes = {}
for p in ("command-center/WORK-UNIT-CATALOG.json", "command-center/PHASE-GRAPH.json",
          "command-center/DEPENDENCY-GRAPH.json", "command-center/COMPLETION-GATES.json",
          "command-center/ARTIFACT-MANIFEST.json", "command-center/TEST-REGISTRY.json",
          "command-center/CLAIM-REGISTRY.json", "platform/schema/receipt.schema.json",
          "platform/schema/artifact-class-profiles.schema.json"):
    fp = os.path.join(REPO, p.replace("/", os.sep))
    sizes[p] = os.path.getsize(fp) if os.path.isfile(fp) else None
out["control_plane_bytes"] = sizes
out["control_plane_bytes_total"] = sum(v for v in sizes.values() if v)

# lines of the catalog if pretty-printed (owner-readability proxy)
txt = json.dumps(cat, indent=1)
out["catalog_prettyprint_lines"] = txt.count("\n") + 1

print(json.dumps(out, indent=1, default=str))
print("SUCCESS:cf-reconcile")
