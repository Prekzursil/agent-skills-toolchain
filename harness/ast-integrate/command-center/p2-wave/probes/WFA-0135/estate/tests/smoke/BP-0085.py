#!/usr/bin/env python3
"""Smoke test for remainder blueprint BP-0085."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ESTATE = HERE.parents[1]
sys.path.insert(0, str(ESTATE.parent))
from runner import execute_from_estate  # noqa: E402

BLUEPRINT_ID = "BP-0085"


def test_smoke() -> dict:
    bp = json.loads((ESTATE / "blueprints" / f"{BLUEPRINT_ID}.json").read_text(encoding="utf-8"))
    assert bp["id"] == BLUEPRINT_ID
    result = execute_from_estate(ESTATE, BLUEPRINT_ID, kind="smoke")
    assert result.get("ok") is True
    return result


if __name__ == "__main__":
    r = test_smoke()
    print(f"PASS {BLUEPRINT_ID} run_id={r['run_id']}")
