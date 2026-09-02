"""AUDIT probe 1: independently discover the catalog shape and the blocked-unit population.

Written by the INDEPENDENT AUDITOR. Does not import or run the builder's scripts.
"""

import io
import json
from collections import Counter

CAT = "command-center/WORK-UNIT-CATALOG.json"


def load(p):
    with io.open(p, encoding="utf-8") as fh:
        return json.load(fh)


d = load(CAT)
wu = d["work_units"]
print("work_units type:", type(wu).__name__, "len:", len(wu))
if isinstance(wu, dict):
    k0 = next(iter(wu))
    print("sample key:", k0)
    print("sample keys of value:", sorted(wu[k0].keys()))
    rows = list(wu.values())
else:
    print("sample keys of value:", sorted(wu[0].keys()))
    rows = wu

# state distribution
for field in ("state", "status", "disposition", "terminal_state"):
    c = Counter(str(r.get(field)) for r in rows)
    if len(c) > 1 or (len(c) == 1 and "None" not in c):
        print(f"\nfield={field}: {dict(c.most_common(20))}")

print("\nwork_units_meta:", json.dumps(d.get("work_units_meta"), indent=1)[:1200])
