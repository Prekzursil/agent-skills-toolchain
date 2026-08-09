"""Cross-unit overlap check across all five workflow-candidate registries.

The 160-candidate program floor is only met if the five units' sets are DISJOINT.
An id collision means two units catalogued the same artifact and the union is
smaller than the sum. This is a set-membership question, so it gets an exact
algorithm, not a judgement call.
"""

import json
from collections import Counter
from pathlib import Path

REG = Path("platform/registry")
files = sorted(REG.glob("workflow-candidates-[0-9].json"))

sets, rows_by_file = {}, {}
for f in files:
    data = json.loads(f.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        print(f"{f.name}: top-level is {type(data).__name__}, not a list -- skipped")
        continue
    ids = []
    for r in data:
        i = r.get("id") or r.get("candidate_id") or r.get("stable_id")
        ids.append(i)
    sets[f.name] = ids
    rows_by_file[f.name] = len(data)

print(f"{'file':<34} {'rows':>6} {'unique ids':>11} {'None ids':>9}")
total = 0
for name, ids in sets.items():
    nn = sum(1 for i in ids if i is None)
    print(f"{name:<34} {rows_by_file[name]:>6} {len(set(i for i in ids if i)):>11} {nn:>9}")
    total += rows_by_file[name]
print(f"{'SUM OF ROWS':<34} {total:>6}")

allids = [i for ids in sets.values() for i in ids if i]
union = set(allids)
print(f"\nunion of ids            : {len(union)}")
print(f"sum of ids              : {len(allids)}")
print(f"collisions (id in >1 row): {len(allids) - len(union)}")

dupes = {k: v for k, v in Counter(allids).items() if v > 1}
if dupes:
    print(f"\n{len(dupes)} colliding id(s):")
    for k, v in sorted(dupes.items(), key=lambda kv: -kv[1])[:40]:
        owners = [n for n, ids in sets.items() if k in ids]
        print(f"  {k:<52} x{v}  in {owners}")
else:
    print("\nNO id collisions -- the five sets are disjoint by id.")

# pairwise
print("\npairwise intersections:")
names = list(sets)
for a in range(len(names)):
    for b in range(a + 1, len(names)):
        inter = set(x for x in sets[names[a]] if x) & set(x for x in sets[names[b]] if x)
        flag = "  <-- OVERLAP" if inter else ""
        print(f"  {names[a]} ^ {names[b]}: {len(inter)}{flag}")
        if inter:
            print(f"      {sorted(inter)[:12]}")

print(f"\nAgainst the 160-candidate program floor: union = {len(union)}")
