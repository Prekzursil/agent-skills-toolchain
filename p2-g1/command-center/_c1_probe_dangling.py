"""LANE C1 read-only probe: do the bucket-form dependencies of the 43 P15/P16 units resolve?

Two resolution routes tried for each token:
  (a) as a unit id  -> exact match on work_units[].id
  (b) as a bucket   -> any work_units[].bucket == token
A token that resolves by neither route is DANGLING: nothing can ever satisfy it.

DETECTOR CONTROL: B02 and B04 are known-present bucket values, so the bucket route must
resolve them. If it does not, the detector is broken and no absence below may be believed.
"""

import json
import re
import collections

d = json.load(open("command-center/WORK-UNIT-CATALOG.json", encoding="utf-8"))
seq = d["work_units"]
ids = {u["id"] for u in seq}
buckets = collections.Counter(u.get("bucket") for u in seq if u.get("bucket"))

p1516 = [u for u in seq if str(u.get("phase")) in ("15", "16")]
print(f"P15/P16 units: {len(p1516)}")

tokens = collections.Counter()
for u in p1516:
    for t in u.get("dependencies") or []:
        tokens[t] += 1

bucket_form = [t for t in tokens if re.fullmatch(r"B\d+", t)]
print("\n### bucket-form dependency tokens used by P15/P16 ###")
dangling = set()
for t in sorted(bucket_form):
    as_id = t in ids
    as_bucket = buckets.get(t, 0)
    ok = as_id or as_bucket
    if not ok:
        dangling.add(t)
    print(f"  {t}: edges={tokens[t]:2d}  as_unit_id={as_id}  as_bucket_members={as_bucket}  "
          f"=> {'RESOLVES' if ok else 'DANGLING'}")

print("\nDETECTOR CONTROL — known-present bucket values must resolve:")
for t in ("B02", "B04", "B10"):
    print(f"  {t}: as_bucket_members={buckets.get(t,0)} -> "
          f"{'detector OK' if buckets.get(t,0) else 'DETECTOR BROKEN'}")

print(f"\nDANGLING tokens: {sorted(dangling)}")
blocked = [u["id"] for u in p1516
           if any(t in dangling for t in (u.get("dependencies") or []))]
print(f"P15/P16 units blocked by >=1 dangling token: {len(blocked)} of {len(p1516)}")
print("  ", blocked)

# also: unit-form deps of P15/P16 that do not exist
unit_form_missing = sorted({t for t in tokens
                            if not re.fullmatch(r"B\d+", t) and t not in ids})
print(f"\nunit-form deps that are not a known unit id: {unit_form_missing}")

# what the catalog's own integrity report claims
kd = d["work_units_meta"]["known_defects_at_merge"]
print("\ncatalog's own integrity claim:")
print("  unknown_form_dependency_refs   =", kd.get("unknown_form_dependency_refs"))
print("  unknown_form_dependency_tokens =", kd.get("unknown_form_dependency_tokens"))
print("  dangling_unit_id_refs          =", kd.get("dangling_unit_id_refs"))
print("  units_missing_bucket_field     =", kd.get("units_missing_bucket_field"))

# transitive: closure of P15/P16 over unit-form deps, how deep does readiness reach?
print("\n### transitive dependency closure of the 43 units (unit-form only) ###")
byid = {u["id"]: u for u in seq}
seen, frontier = set(), [u["id"] for u in p1516]
while frontier:
    nxt = []
    for i in frontier:
        for t in (byid.get(i, {}).get("dependencies") or []):
            if t in byid and t not in seen:
                seen.add(t)
                nxt.append(t)
    frontier = nxt
print(f"closure size (excluding the 43 themselves): {len(seen - {u['id'] for u in p1516})}")
ph = collections.Counter(str(byid[i]["phase"]) for i in seen)
print("closure by phase:", dict(sorted(ph.items(), key=lambda x: x[0])))
