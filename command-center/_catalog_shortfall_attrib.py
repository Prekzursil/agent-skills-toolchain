#!/usr/bin/env python3
"""Attribute the 2048-vs-actual shortfall to specific buckets, mechanically.

Hypothesis to test: each id-prefix family maps 1:1 onto one of the 13 spec allocation
buckets (PHASE-GRAPH.json allocation_buckets), and the shortfall is concentrated in the
families whose count is below their bucket quota. The test is exact-arithmetic, not
judgement: if the per-family deficits do not sum to the global shortfall, the hypothesis
is REFUTED and the mapping is wrong.
"""
import json
import os
import sys
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _catalog_integrity as ci  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
units, _ = ci.load_dir(ci.SLICES)

pref = collections.Counter()
for u in units:
    m = ci.ID_RE.match(str(u.get("id")))
    pref[m.group(1) if m else "UNKNOWN"] += 1

quota = ci.BUCKET_QUOTA
# Derive the family -> bucket mapping from EVIDENCE, not assertion:
#  (a) the `bucket` field where a slice declares one;
#  (b) otherwise the unique bucket whose quota equals the family size (exact match);
#  (c) otherwise leave UNMAPPED and say so.
declared = collections.defaultdict(collections.Counter)
for u in units:
    b = u.get("bucket")
    m = ci.ID_RE.match(str(u.get("id")))
    if isinstance(b, str) and m:
        declared[m.group(1)][b] += 1

max_id = {}
for p in sorted(pref):
    ns = [int(ci.ID_RE.match(str(u["id"])).group(2)) for u in units
          if ci.ID_RE.match(str(u["id"])) and ci.ID_RE.match(str(u["id"])).group(1) == p]
    max_id[p] = max(ns) if ns else 0

# Semantic hint from the bucket NAME, used only as corroboration / tie-break.
NAME_HINT = {"CC": "command-center", "REL": "release", "IMP": "implementation",
             "RES": "research", "ADV": "adversarial", "TST": "testing", "CNF": "confirmation",
             "ARC": "architecture", "AUD": "audit", "BLD": "blind-spot", "CNL": "council",
             "SYN": "synthesis", "WFA": "workflow"}
bucket_name = {b["id"]: b["name"] for b in json.load(
    open(os.path.join(HERE, "PHASE-GRAPH.json"), encoding="utf-8")
)["allocation_buckets"]["buckets"]}

mapping = {}
basis = {}
# pass 1 - declared bucket field (strongest evidence)
for p, n in sorted(pref.items()):
    if declared.get(p):
        b = declared[p].most_common(1)[0][0]
        mapping[p] = b
        basis[p] = f"declared `bucket` field on {declared[p][b]}/{n} units"
# pass 2 - unique bucket whose quota EXACTLY equals the family size. NOTE: this rule is
# structurally blind to the families that are SHORT (their size cannot equal their quota),
# which is why pass 3 exists. Relying on pass 2 alone reports a 0 deficit everywhere and
# refutes its own hypothesis.
taken = set(mapping.values())
for p, n in sorted(pref.items()):
    if p in mapping:
        continue
    exact = [b for b, q in quota.items() if q == n and b not in taken]
    if len(exact) == 1:
        mapping[p] = exact[0]
        taken.add(exact[0])
        basis[p] = f"unique unclaimed bucket whose quota == family size ({n})"
# pass 3 - max AUTHORED id == quota (decisive: the family numbered itself to its quota),
# then semantic name, then elimination when a single candidate remains.
for p, n in sorted(pref.items()):
    if p in mapping:
        continue
    free = [b for b in quota if b not in taken]
    bymax = [b for b in free if quota[b] == max_id[p]]
    if len(bymax) == 1:
        mapping[p] = bymax[0]
        taken.add(bymax[0])
        basis[p] = (f"max authored id {p}-{max_id[p]:04d} == bucket quota "
                    f"{quota[bymax[0]]}; family numbered itself to the quota")
        continue
    hint = NAME_HINT.get(p, "")
    byname = [b for b in free if hint and hint in bucket_name[b].lower()]
    if len(byname) == 1:
        mapping[p] = byname[0]
        taken.add(byname[0])
        basis[p] = (f'bucket name "{bucket_name[byname[0]]}" matches family hint '
                    f'"{hint}" (quota {quota[byname[0]]})')
        continue
    if len(free) == 1:
        mapping[p] = free[0]
        taken.add(free[0])
        basis[p] = f"elimination: only unclaimed bucket left ({free[0]})"
        continue
    mapping[p] = None
    basis[p] = f"UNMAPPED: candidates {free}"

used = collections.Counter(v for v in mapping.values() if v)
collisions = {b: c for b, c in used.items() if c > 1}
unclaimed = sorted(set(quota) - set(v for v in mapping.values() if v))

rows = []
for p, n in sorted(pref.items()):
    b = mapping[p]
    q = quota.get(b) if b else None
    rows.append({"family": p, "units": n, "bucket": b, "quota": q,
                 "deficit": (q - n) if q is not None else None,
                 "mapping_basis": basis[p]})

deficit_sum = sum(r["deficit"] for r in rows if r["deficit"])
global_short = ci.TARGET_UNITS - len(units)

# per-family numbering holes (a family can be short by never authoring mid-range ids)
holes = {}
for p in sorted(pref):
    ns = sorted(int(ci.ID_RE.match(str(u["id"])).group(2)) for u in units
                if ci.ID_RE.match(str(u["id"])) and ci.ID_RE.match(str(u["id"])).group(1) == p)
    gaps = sorted(set(range(1, max(ns) + 1)) - set(ns))
    if gaps:
        holes[p] = {"max_id": max(ns), "count": len(ns), "missing_ids":
                    [f"{p}-{g:04d}" for g in gaps]}

out = {
    "total_units": len(units),
    "target": ci.TARGET_UNITS,
    "global_shortfall": global_short,
    "spec_quota_sum": sum(quota.values()),
    "family_rows": rows,
    "sum_of_family_deficits": deficit_sum,
    "deficits_explain_shortfall_exactly": deficit_sum == global_short,
    "verdict": ("CONFIRMED: per-family deficits sum exactly to the global shortfall"
                if deficit_sum == global_short else
                f"REFUTED: deficits sum to {deficit_sum}, shortfall is {global_short}"),
    "bucket_mapping_collisions": collisions,
    "buckets_with_no_family": unclaimed,
    "numbering_holes": holes,
}
with open(os.path.join(HERE, "_catalog_shortfall_attrib_out.json"), "w",
          encoding="utf-8") as fh:
    json.dump(out, fh, ensure_ascii=False, indent=1)

print(f"total={out['total_units']} target={out['target']} "
      f"shortfall={out['global_shortfall']}")
print(f"spec quota sum={out['spec_quota_sum']}")
print()
print(f"{'family':8s} {'units':>6s} {'bucket':>7s} {'quota':>6s} {'deficit':>8s}  basis")
for r in rows:
    print(f"{r['family']:8s} {r['units']:6d} {str(r['bucket']):>7s} "
          f"{str(r['quota']):>6s} {str(r['deficit']):>8s}  {r['mapping_basis']}")
print()
print("sum of family deficits =", deficit_sum, "| global shortfall =", global_short)
print("VERDICT:", out["verdict"])
print("mapping collisions:", collisions or "none")
print("buckets with no id-family:", unclaimed or "none")
print()
print("NUMBERING HOLES (ids the family skipped):")
for p, h in holes.items():
    ids = h["missing_ids"]
    print(f"  {p}: count={h['count']} max={p}-{h['max_id']:04d} "
          f"missing {len(ids)}: {ids[:12]}{'...' if len(ids) > 12 else ''}")
if not holes:
    print("  none")
