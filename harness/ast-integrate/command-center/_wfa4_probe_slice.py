"""Dump the canonical-order slice for unit build/wfa-4 (positions 97-128, 1-indexed)."""

import json
import pathlib

P = pathlib.Path(
    r"C:/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json"
)
doc = json.loads(P.read_text(encoding="utf-8"))
c = doc["candidates"]
print(f"total={len(c)}")
# family boundaries in array order
prev = None
for i, e in enumerate(c, start=1):
    if e["family"] != prev:
        print(f"  family {e['family']} starts at position {i}")
        prev = e["family"]
print()
print("=== positions 90..135 ===")
for i in range(90, min(136, len(c) + 1)):
    e = c[i - 1]
    print(
        f"{i:3d} | {e['family']:18s} | {e['classification']:22s} | {e['id']:52s} | {e['name'][:44]}"
    )
print()
print("=== full records for 97..128 ===")
for i in range(97, 129):
    e = c[i - 1]
    print(f"\n----- pos {i} -----")
    print(json.dumps(e, indent=1, ensure_ascii=False))
