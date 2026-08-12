"""LANE C1 read-only probe: the 31 phase-15 + 12 phase-16 units, and whether their
declared output_path exists on disk.

READ-ONLY.
"""

import json
import os

d = json.load(open("command-center/WORK-UNIT-CATALOG.json", encoding="utf-8"))
seq = d["work_units"]
print("contract keys:", list(d["contract"].keys()) if isinstance(d["contract"], dict) else "?")
print("terminal_dispositions:", json.dumps(d.get("terminal_dispositions"))[:400])
print("work_units_meta:", json.dumps(d.get("work_units_meta"))[:600])
print()

# any disposition-like field on a unit?
u0 = seq[0]
print("unit0 fields:", sorted(u0.keys()))
print("unit0 sample:", json.dumps(u0, indent=1)[:1200])
print("=" * 78)

for want in ("15", "16"):
    us = [u for u in seq if str(u.get("phase")) == want]
    print(f"\n######## PHASE {want}: {len(us)} units ########")
    for u in us:
        op = u.get("output_path")
        exists = "EXISTS" if (op and os.path.exists(op)) else "MISSING"
        print(f"{u['id']} | {exists} | {op}")
        print(f"    title: {u.get('title')}")
        print(f"    anchor: {u.get('spec_anchor')}  schema: {u.get('output_schema')}")
        print(f"    sentinel: {str(u.get('completion_sentinel'))[:220]}")
        print(f"    owner_approval_required: {u.get('owner_approval_required')}"
              f"  deps: {u.get('dependencies')}")
