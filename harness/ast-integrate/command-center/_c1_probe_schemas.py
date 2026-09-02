"""LANE C1 read-only probe: schema existence + all REL units + bucket deps for P15/P16."""

import json
import os
import re
import collections

d = json.load(open("command-center/WORK-UNIT-CATALOG.json", encoding="utf-8"))
seq = d["work_units"]

p1516 = [u for u in seq if str(u.get("phase")) in ("15", "16")]

# --- 1. schema existence (detector control: assert a known-present schema is found) ---
schemas = collections.Counter()
for u in p1516:
    s = (u.get("output_schema") or "").split()[0].split("#")[0]
    if s:
        schemas[s] += 1
print("### SCHEMAS referenced by the 43 P15/P16 units ###")
for s, n in sorted(schemas.items()):
    print(f"{'EXISTS ' if os.path.exists(s) else 'MISSING'} | x{n:2d} | {s}")

ctrl = "command-center/WORK-UNIT-CATALOG.json"
print(f"\nDETECTOR CONTROL (known-present path): os.path.exists({ctrl}) = {os.path.exists(ctrl)}")
print("schema dir listing:")
sd = "command-center/schema"
if os.path.isdir(sd):
    names = sorted(os.listdir(sd))
    print(f"  {len(names)} files in {sd}")
    for n in names:
        print("   ", n)
else:
    print("  MISSING dir", sd)

# --- 2. all REL units, any phase ---
print("\n### ALL REL-* units by phase ###")
rel = [u for u in seq if str(u.get("id", "")).startswith("REL-")]
for u in sorted(rel, key=lambda x: x["id"]):
    print(f"{u['id']} | phase {u.get('phase')} | owner_gate={u.get('owner_approval_required')} | "
          f"{u.get('title')[:80]}")

# --- 3. what are the B-bucket dependencies? ---
deps = collections.Counter()
for u in p1516:
    for dep in u.get("dependencies") or []:
        deps[dep] += 1
print("\n### dependencies of the 43 P15/P16 units (count) ###")
for k, v in sorted(deps.items(), key=lambda x: (-x[1], x[0])):
    print(f"  {k}: {v}")

# resolve non-B deps to their unit + phase
ids = {u["id"]: u for u in seq}
print("\n### unit-form deps resolved ###")
for k in sorted(deps):
    if re.match(r"^B\d+$", k):
        continue
    u = ids.get(k)
    print(f"  {k} -> {'phase ' + str(u.get('phase')) if u else 'UNRESOLVED / not a unit id'}"
          f"{' | ' + u.get('title')[:70] if u else ''}")

# --- 4. bucket definitions in catalog? ---
print("\n### bucket field values among P15/P16 ###")
print(collections.Counter(str(u.get("bucket")) for u in p1516))
print("\ncontract.reachability_rule:", json.dumps(d["contract"].get("reachability_rule"))[:600])
