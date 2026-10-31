"""Producer rejects duplicate JSON keys (TST-0054)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / ".." / "lib"))

import strict_json as sj  # noqa: E402


def test_duplicate_key_is_rejected_by_the_producer() -> dict:
    fixture = '{"name":"first","name":"second"}'
    try:
        sj.loads_strict(fixture)
        ok = False
        err = None
    except Exception as exc:
        ok = type(exc).__name__ in {"DuplicateKeyError", "StrictJSONError"} or "duplicate" in str(exc).lower()
        err = exc
    return {"ok": ok, "error": str(err)}
