"""Throwaway probe: what does population-classified.json actually say, and does
CLAUDE.md's prose agree with it?  Read-only.  Not a gate; it exists to decide whether
a gate is needed.

DETECTOR FAILURE, recorded rather than deleted: the first version of this file picked
"the first top-level list of dicts" and landed on ``referenced_by_exec_config`` (len 3),
then reported "distinct store values: 1" and "rows with unpushed/dirty/staged: 0".  Both
numbers were real readings of the WRONG collection -- the same one-level-above mistake
that made ``manifest["events"][ev]`` report 3-and-3 on both sides earlier in this program.
It now names ``rows`` explicitly and asserts its length against ``population``.
"""

import json
import pathlib
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[2]
pc = json.loads(
    (ROOT / "command-center/ssot/population-classified.json").read_text(
        encoding="utf-8"
    )
)

print("=== scalars and list-lengths at top level ===")
for k, v in pc.items():
    if isinstance(v, list):
        print(f"  {k:34s} LIST len={len(v)}")
    elif isinstance(v, dict):
        print(f"  {k:34s} DICT {json.dumps(v)[:160]}")
    else:
        print(f"  {k:34s} {v}")

rows = pc["rows"]
assert isinstance(rows, list) and rows and isinstance(rows[0], dict), (
    "rows is not a row list"
)
print(f"\n=== rows (explicitly named, len={len(rows)}) ===")
print("row keys:", sorted(rows[0].keys()))
# CONTROL: the collection must be the population-sized one, not a 3-element sub-list.
print(
    "CONTROL len(rows) == population:",
    len(rows) == pc["population"],
    f"({len(rows)} vs {pc['population']})",
)

for field in ("kind", "signals_agree"):
    print(f"  {field}: {dict(Counter(json.dumps(r.get(field)) for r in rows))}")

cand = sorted(
    k
    for k in rows[0]
    if any(
        t in k for t in ("dirty", "unpush", "stag", "remote", "store", "commit", "uniq")
    )
)
print("  candidate content fields:", cand)
for c in cand:
    vals = [r.get(c) for r in rows]
    kinds = Counter(type(v).__name__ for v in vals)
    nz = sum(
        1
        for v in vals
        if (
            v
            if isinstance(v, bool)
            else (v or 0)
            if isinstance(v, (int, float))
            else bool(v)
        )
    )
    print(f"    {c:26s} types={dict(kinds)} truthy/nonzero={nz}")
