#!/usr/bin/env python3
"""Discriminating collector: catalog path vs spec-alias / harvest copies."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CANDIDATES = [
    "command-center/synthesis/SYN-0001.root-cause-hierarchy.json",
    "command-center/synthesis/ROOT-CAUSE-HIERARCHY.json",
    "command-center/synthesis/ROOT-CAUSE-HIERARCHY.json".replace("synthesis", "receipts"),
]


def main() -> int:
    rows = []
    for rel in CANDIDATES:
        p = REPO / rel
        rows.append(
            {
                "path": rel,
                "present": p.is_file(),
                "bytes": p.stat().st_size if p.is_file() else 0,
            }
        )
    syn = REPO / "command-center/synthesis"
    listing = sorted(p.name for p in syn.iterdir()) if syn.is_dir() else []
    found = [r for r in rows if r["present"]]
    print(
        json.dumps(
            {
                "collector": "hierarchy-paths",
                "catalog_path_present": rows[0]["present"],
                "alias_or_harvest_present": any(r["present"] for r in rows[1:]),
                "rows": rows,
                "synthesis_listing": listing,
                "verdict": (
                    "alias-or-harvest"
                    if (not rows[0]["present"] and found)
                    else ("skipped-unit" if not found else "catalog-path-hit")
                ),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
