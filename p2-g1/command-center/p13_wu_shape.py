"""P13: work-unit shape + disposition census. Read-only."""

from __future__ import annotations

import collections
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
CC = REPO / "command-center"


def main() -> int:
    cat = json.loads((CC / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    wus = cat["work_units"]
    items = cat["items"]

    print("=== work_units[0] full ===")
    print(json.dumps(wus[0], indent=2)[:3000])

    print()
    print("=== field presence across 2007 work_units ===")
    fields: collections.Counter = collections.Counter()
    for w in wus:
        for k in w:
            fields[k] += 1
    for k, n in fields.most_common():
        print(f"  {n:5d}/{len(wus)}  {k}")

    print()
    print("=== any status/disposition-like field on work_units? ===")
    for k in fields:
        if any(
            t in k.lower()
            for t in ("status", "disp", "state", "done", "exec", "result", "receipt")
        ):
            vals = collections.Counter(str(w.get(k))[:60] for w in wus)
            print(f"  {k}: {dict(list(vals.most_common(8)))}")

    print()
    print("=== items[] disposition census (103 backlog items) ===")
    dc = collections.Counter(i.get("disposition") for i in items)
    for k, n in dc.most_common():
        print(f"  {n:4d}  {k}")

    print()
    print("=== items[0] full ===")
    print(json.dumps(items[0], indent=2)[:2500])

    print()
    print("=== work_unit id prefixes (bucket census) ===")
    bc = collections.Counter(w.get("bucket") for w in wus)
    for k, n in bc.most_common(40):
        print(f"  {n:5d}  {k}")

    print()
    print("=== phase census on work_units ===")
    if "phase" in fields:
        pc = collections.Counter(str(w.get("phase")) for w in wus)
        for k, n in sorted(pc.items(), key=lambda kv: -kv[1])[:40]:
            print(f"  {n:5d}  {k}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
