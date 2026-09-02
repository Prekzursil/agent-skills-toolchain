#!/usr/bin/env python3
"""IMP-0237 probe 1: watchlist two-run idempotence (zero duplicate findings)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "tools" / "research_blueprints" / "tests"))

from test_imp0237 import run_all  # noqa: E402


def main() -> int:
    result = run_all()
    watch = result["rows"]["watchlist"]
    schedule = result["rows"]["schedule"]
    archival = result["rows"]["archival"]
    contract = result["rows"]["contract"]
    payload = {
        "id": "watchlist-idempotence",
        "pass": bool(
            watch["pass"] and schedule["pass"] and archival["pass"] and contract["pass"]
        ),
        "watchlist": watch,
        "schedule": schedule,
        "archival": archival,
        "contract": contract,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not payload["pass"]:
        print("FAILED:IMP-0237-probe1 watchlist idempotence")
        return 1
    print(
        f"first_new={watch['first_new']} second_new={watch['second_new']} "
        f"duplicates={watch['second_duplicates']} scheduled={schedule['scheduled']}"
    )
    print("SUCCESS:IMP-0237-probe1 watchlist idempotent across two runs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
