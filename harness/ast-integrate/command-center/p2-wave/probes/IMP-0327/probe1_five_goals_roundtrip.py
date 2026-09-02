#!/usr/bin/env python3
"""IMP-0327 probe 1: five owner goals round-trip and fixtures stop for the stated reason."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "tools" / "council" / "tests"))

from test_builder import (  # noqa: E402
    test_five_goals_roundtrip,
    test_fixtures_stop_for_stated_reason,
)


def main() -> int:
    rt = test_five_goals_roundtrip()
    fx = test_fixtures_stop_for_stated_reason()
    printed = [
        {"goal_id": row["goal_id"], "phrasing": row["phrasing"], "printed": row["printed"]}
        for row in rt["rows"]
    ]
    payload = {
        "probe": "probe1-five-goals-roundtrip",
        "unit_id": "IMP-0327",
        "roundtrip": rt,
        "fixtures": fx,
        "stopping_expressions_printed": printed,
        "pass": bool(rt["pass"] and fx["pass"]),
    }
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    if not payload["pass"]:
        print("FAILED:IMP-0327-probe1 five-goals roundtrip or fixture stop-reason")
        return 1
    print(
        "SUCCESS:IMP-0327-probe1 five goals round-tripped; "
        "each stopping expression printed; fixtures stop for the stated reason"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
