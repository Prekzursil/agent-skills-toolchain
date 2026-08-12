r"""Blast radius of the existence-only `delivered()` detector in ready_units.py.

ready_units.py satisfies a dependency edge when the dep's output_path EXISTS. Measured: all 42
existing artifacts self-declare state=BLOCKED (37) / FAILED (4) / no-state (1). None declares
DELIVERED. So every dependency edge pointing at one of those 42 is satisfied by a file that says
it is not done.

This probe answers: how many units are READY *only because* such an edge was counted satisfied?
It re-runs the same partition under a STRICTER delivered() (exists AND state not in
{BLOCKED, FAILED} AND size >= a floor) and diffs the READY set.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"
BUCKET = re.compile(r"B\d+")
NOT_DONE = {"BLOCKED", "FAILED", "SKELETON"}


def partition(strict: bool):
    doc = json.loads(CATALOG.read_text(encoding="utf-8"))
    units = doc["work_units"]
    by_id = {u["id"]: u for u in units}

    def delivered(uid: str) -> bool:
        u = by_id.get(uid)
        if not u:
            return False
        p = u.get("output_path")
        if not p:
            return False
        fp = REPO / p
        if not fp.exists():
            return False
        if not strict:
            return True
        if fp.stat().st_size < 200:
            return False
        if p.endswith(".json"):
            try:
                d = json.loads(fp.read_text(encoding="utf-8"))
            except Exception:
                return False
            if str(d.get("state", "")).upper() in NOT_DONE:
                return False
        return True

    ready = []
    for u in units:
        if delivered(u["id"]):
            continue
        if u.get("owner_approval_required"):
            continue
        ok = True
        for dep in u.get("dependencies") or []:
            if BUCKET.fullmatch(dep):
                continue
            if dep in by_id:
                if not delivered(dep):
                    ok = False
                    break
            else:
                ok = False
                break
        if ok:
            ready.append(u["id"])
    return set(ready), by_id


def main() -> int:
    loose, by_id = partition(strict=False)
    strict, _ = partition(strict=True)
    print(f"READY under existence-only delivered(): {len(loose)}")
    print(f"READY under state-aware delivered():    {len(strict)}")
    phantom = sorted(loose - strict)
    gained = sorted(strict - loose)
    print(
        f"\nPHANTOM-READY (ready only because a BLOCKED/FAILED artifact counted as done): {len(phantom)}"
    )
    for uid in phantom[:25]:
        deps = by_id[uid].get("dependencies") or []
        print(f"  {uid:<10} deps={deps}")
    if len(phantom) > 25:
        print(f"  ... and {len(phantom) - 25} more")
    print(
        f"\nNEWLY-READY under strict (self-declared-done units re-enter the build set): {len(gained)}"
    )
    for uid in gained[:15]:
        print(f"  {uid}")
    print(
        f"\nSUCCESS:blast-radius phantom={len(phantom)} loose={len(loose)} strict={len(strict)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
