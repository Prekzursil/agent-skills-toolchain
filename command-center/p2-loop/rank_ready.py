#!/usr/bin/env python3
"""Rank READY units by OQ-2: ascending integer phase, then unblocking power, then id."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"
READY = REPO / "command-center/READY-UNITS.json"


def phase_key(phase: object) -> tuple[int, str]:
    s = "" if phase is None else str(phase)
    m = re.match(r"^(\d+)", s)
    return (int(m.group(1)) if m else 99, s)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    cat = {
        u["id"]: u
        for u in json.loads(CATALOG.read_text(encoding="utf-8"))["work_units"]
    }
    ready = json.loads(READY.read_text(encoding="utf-8"))["ready_units"]
    power: Counter[str] = Counter()
    for u in cat.values():
        for dep in u.get("dependencies") or []:
            if dep in cat:
                power[dep] += 1

    ranked = sorted(ready, key=lambda i: (phase_key(cat[i].get("phase")), -power[i], i))
    rows = []
    for i in ranked[: args.limit]:
        u = cat[i]
        rows.append(
            {
                "id": i,
                "phase": u.get("phase"),
                "power": power[i],
                "substrate": u.get("execution_substrate"),
                "output_path": u["output_path"],
                "title": u.get("title"),
            }
        )
    if args.json:
        json.dump({"ranked": rows, "ready_total": len(ready)}, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        print(f"READY={len(ready)} showing {len(rows)}")
        for r in rows:
            print(
                f"{r['id']:12} phase={str(r['phase']):4} power={r['power']:3} "
                f"{r['substrate']}  {r['title'][:70]}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
