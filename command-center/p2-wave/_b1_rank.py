r"""BUILD-lane ranking probe: ascending phase (INT), then unblocking power (OQ-2 owner ruling).

Fixes the grounding lane's disclosed lexicographic-phase bug by using an int key.
Prints the top-N READY units with the FULL catalog row fields the build needs.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"
BUCKET = re.compile(r"B\d+")


def phase_key(p: object) -> tuple[int, str]:
    s = str(p)
    m = re.match(r"(\d+)", s)
    return (int(m.group(1)) if m else 9999, s)


def main() -> int:
    doc = json.loads(CATALOG.read_text(encoding="utf-8"))
    units = doc["work_units"]
    by_id = {u["id"]: u for u in units}

    def exists(u: dict) -> bool:
        p = u.get("output_path")
        return bool(p) and (REPO / p).exists()

    ready = []
    for u in units:
        if exists(u):
            continue
        if u.get("owner_approval_required"):
            continue
        bad = False
        for dep in u.get("dependencies") or []:
            if BUCKET.fullmatch(dep):
                continue
            if dep in by_id:
                if not exists(by_id[dep]):
                    bad = True
                    break
            else:
                bad = True
                break
        if not bad:
            ready.append(u)

    # unblocking power: how many OTHER units name this one as a dependency
    dependents: Counter = Counter()
    for u in units:
        for dep in u.get("dependencies") or []:
            dependents[dep] += 1

    ready.sort(key=lambda u: (phase_key(u.get("phase")), -dependents[u["id"]], u["id"]))

    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    print(f"READY={len(ready)}  (catalog units={len(units)})")
    print("-" * 100)
    for u in ready[:n]:
        print(
            f"{u['id']:>10}  phase={str(u.get('phase')):<4} unblocks={dependents[u['id']]:<3} "
            f"out={u.get('output_path')}"
        )
    print("-" * 100)
    print("PHASE-0 READY count:", sum(1 for u in ready if phase_key(u.get("phase"))[0] == 0))
    # control: the sort key must place '2' before '10'
    ctl = sorted(["10", "2", "0", "2A"], key=phase_key)
    print("CONTROL phase-sort:", ctl, "->", "OK" if ctl == ["0", "2", "2A", "10"] else "BROKEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
