"""Round-4 survey: locate the three CONFIRMED defects exactly, before touching anything.

Read-only. Prints, for each defect, the current state and the control that proves the
reader is looking at the right collection (single-signal-verification rule 3c: a control
that cannot distinguish the two hypotheses is not a control).
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
POP = ROOT / "command-center" / "ssot" / "population-classified.json"
INV = ROOT / "docs" / "ssot" / "SSOT-CLONE-INVENTORY.md"
CLAUDE = ROOT / "CLAUDE.md"


def read_text(p: pathlib.Path) -> str:
    return p.read_text(encoding="utf-8", newline="")


def main() -> int:
    pop = json.loads(read_text(POP))

    rows = pop.get("checkouts") or pop.get("rows") or []
    if not rows:
        # discover the list-of-dicts key holding per-checkout rows
        for k, v in pop.items():
            if isinstance(v, list) and v and isinstance(v[0], dict) and "kind" in v[0]:
                rows = v
                print(f"rows key discovered: {k}")
                break

    print(f"top-level keys      : {sorted(pop.keys())}")
    print(f"row count           : {len(rows)}")
    if not rows:
        print("FAILED: no per-checkout rows found - reader is on the wrong collection")
        return 1

    # CONTROL: the reader must be able to see BOTH kinds, else 'all agree' is vacuous.
    kinds: dict[str, int] = {}
    for r in rows:
        kinds[str(r.get("kind"))] = kinds.get(str(r.get("kind")), 0) + 1
    print(f"kind histogram      : {kinds}")
    agree = sum(1 for r in rows if r.get("signals_agree") is True)
    disagree = [r for r in rows if r.get("signals_agree") is not True]
    print(f"signals_agree True  : {agree}")
    print(f"signals_agree not-True: {len(disagree)}")
    control_ok = len(kinds) >= 2 and agree > 0
    print(f"CONTROL kinds>=2 and agree>0 -> discriminates={control_ok}")

    for r in disagree:
        print("\nDISAGREE ROW:")
        print(json.dumps(r, indent=2)[:1600])

    # summary block, if present
    for k in ("summary", "totals", "counts"):
        if k in pop:
            print(f"\n{k}: {json.dumps(pop[k], indent=2)[:1200]}")

    # DEFECT 2: the CLAUDE.md arithmetic
    ct = read_text(CLAUDE)
    m = re.search(r"\*\*(\d+) checkouts across (\d+) object stores\*\*[^\n]*", ct)
    print("\n--- CLAUDE.md arithmetic sentence ---")
    if m:
        seg = ct[m.start() : m.start() + 400].replace("\r\n", "\n")
        print(seg)
        nums = [int(x) for x in re.findall(r"\b(\d+)\b", seg)]
        print(f"numbers in segment: {nums}")
    else:
        print("NOT FOUND - the wiring sentence changed shape")

    # DEFECT 1: the DoD-1 sentence in the inventory
    it = read_text(INV).replace("\r\n", "\n")
    print("\n--- inventory lines mentioning 178/178 or 'two agreeing signals' ---")
    for i, line in enumerate(it.split("\n"), 1):
        if "178/178" in line or "agreeing signals" in line or "disagree" in line:
            print(f"{INV.name}:{i}: {line.strip()[:300]}")

    print("\n--- CLAUDE.md lines mentioning worktrees/clones counts ---")
    for i, line in enumerate(ct.replace("\r\n", "\n").split("\n"), 1):
        if re.search(r"linked worktrees|independent clones|object stores", line):
            print(f"CLAUDE.md:{i}: {line.strip()[:300]}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
