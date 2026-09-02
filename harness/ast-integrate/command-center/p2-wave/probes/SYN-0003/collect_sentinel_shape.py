#!/usr/bin/env python3
"""Discriminating collector: catalog sentinel paragraph vs short token."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"
MEASURE = REPO / "command-center/p2-wave/_measure_one_delivered.py"


def main() -> int:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    unit = next(u for u in data["work_units"] if u.get("id") == "SYN-0003")
    sent = str(unit.get("completion_sentinel") or "")
    src = MEASURE.read_text(encoding="utf-8")
    print(
        json.dumps(
            {
                "collector": "sentinel-shape",
                "sentinel_len": len(sent),
                "starts_with_success_token": sent.startswith("SUCCESS:SYN-0003"),
                "is_paragraph": len(sent) > 40,
                "measure_requires_catalog_substring": "completion_sentinel" in src
                and "sentinel-absent" in src,
                "short_token": "SUCCESS:SYN-0003",
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
