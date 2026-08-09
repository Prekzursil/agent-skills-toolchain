"""Probe the prior archaeology registry structure. Read-only."""

import json
import sys
from collections import Counter

SRC = r"C:\Users\Prekzursil\.claude\harness-restore-20260806\08-WORKFLOW-CANDIDATE-REGISTRY.json"

with open(SRC, encoding="utf-8") as fh:
    data = json.load(fh)

print("top-level type:", type(data).__name__)
if isinstance(data, dict):
    print("keys:", list(data.keys()))
    for k, v in data.items():
        print(f"  {k}: {type(v).__name__}", end="")
        if isinstance(v, (list, dict)):
            print(f" len={len(v)}")
        else:
            print(f" = {v!r}"[:160])
    # find the candidate list
    for k, v in data.items():
        if isinstance(v, list) and v and isinstance(v[0], dict):
            print(f"\n--- list '{k}' n={len(v)} ---")
            print("field union:", sorted({f for row in v for f in row}))
            print("\nfirst row:")
            print(json.dumps(v[0], indent=2, ensure_ascii=False)[:3000])
            fams = Counter(row.get("family") for row in v)
            print("\nfamily counts:", dict(fams))
            cls = Counter(row.get("classification") for row in v)
            print("classification counts:", dict(cls))
elif isinstance(data, list):
    print("n=", len(data))
    print("field union:", sorted({f for row in data for f in row if isinstance(row, dict)}))
    print(json.dumps(data[0], indent=2, ensure_ascii=False)[:3000])

sys.stdout.flush()
