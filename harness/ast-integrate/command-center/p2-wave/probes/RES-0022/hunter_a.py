#!/usr/bin/env python3
"""Hunter A: plugin/marketplace/hooks partition (S01-S10). Does not import hunter_b."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from measure import measure_one  # noqa: E402
from statements import partition  # noqa: E402

OUT = HERE / "hunter_a.json"


def main() -> int:
    rows = [measure_one(s["id"]) for s in partition("A")]
    payload = {
        "reviewer_id": "RES-0022-hunter-A-plugin-hooks",
        "independent": True,
        "partition": [r["id"] for r in rows],
        "sibling_prose_read": False,
        "rows": rows,
    }
    OUT.write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"hunter_a rows={len(rows)} -> {OUT.name}")
    for row in rows:
        print(f"  {row['id']} {row['verdict']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
