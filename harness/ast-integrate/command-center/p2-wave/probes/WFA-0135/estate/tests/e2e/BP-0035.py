#!/usr/bin/env python3
"""Flagship end-to-end test for BP-0035."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ESTATE = HERE.parents[1]
sys.path.insert(0, str(ESTATE.parent))
from runner import execute_from_estate  # noqa: E402

BLUEPRINT_ID = "BP-0035"


def test_end_to_end() -> dict:
    result = execute_from_estate(ESTATE, BLUEPRINT_ID, kind="e2e")
    art = Path(result["artifact_path"])
    # FLAGSHIP_E2E_ANCHOR
    assert art.is_file(), "missing produced artifact"
    assert art.stat().st_size >= 32, "artifact too small"
    payload = json.loads(art.read_text(encoding="utf-8"))
    assert payload.get("ok") is True
    assert payload.get("blueprint_id") == BLUEPRINT_ID
    return result


if __name__ == "__main__":
    r = test_end_to_end()
    print(f"PASS {BLUEPRINT_ID} run_id={r['run_id']}")
