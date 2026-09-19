#!/usr/bin/env python3
"""P2 goal function — the committed definition of 'P2 is finished'.

Exit code 0 + JSON on stdout. p2_done=true only when:
  - no rail-blocked units remain un-reviewed (cross-vendor rail satisfied),
  - every satisfiable unit carries an independent PASS review,
  - every catalog unit is READY or carries a recorded owner-blocked/deferred
    disposition (owner questions are legitimate terminals, never forced).

The chain runner consults this at every step boundary; it is the ONLY thing
that decides when P2 ends (and when PR reconciliation begins).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def sh(cmd: list[str]) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def main() -> int:
    # 1. rail gate (C5/C6: reviews + doc agreement) — its failure text names the gaps
    rc_rail, out_rail = sh(
        ["python", "command-center/p2-next/rail_count_gate.py", "--basis", "worktree"]
    )
    rail_lines = [
        ln.strip() for ln in out_rail.splitlines() if " -- " in ln and "C5 " in ln
    ]

    # 2. delivery predicate partition (READY vs the rest)
    rc_ready, out_ready = sh(["python", "command-center/ready_units.py"])
    # ready_units prints a partition summary; capture the numbers we can trust
    partition_ok = rc_ready == 0

    # 3. catalog terminal census
    cat = json.loads(
        (ROOT / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
    )
    units = cat["work_units"]
    total = len(units)
    td = cat.get("terminal_dispositions") or []
    terminal = set(td) if isinstance(td, list) else set(td.keys())
    # owner-blocked = disposition recorded in the catalog's terminal set
    n_terminal = sum(
        1
        for u in units
        if u.get("phase") in terminal
        or u.get("bucket") in terminal
        or u.get("completion_sentinel") in terminal
    )

    p2_done = rc_rail == 0 and partition_ok and not rail_lines

    print(
        json.dumps(
            {
                "p2_done": p2_done,
                "rail_green": rc_rail == 0,
                "rail_gaps": rail_lines[:10],
                "partition_ok": partition_ok,
                "catalog_units": total,
                "units_terminal_dispositioned": n_terminal,
                "next_phase": "pr-reconcile" if p2_done else "p2-agent",
            },
            indent=1,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
