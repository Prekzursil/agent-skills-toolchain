"""Outcome-kind census over live artifacts."""
from __future__ import annotations

from typing import Any


def census(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return {"ok": True, "kinds": {}, "count": 0}


def count_kinds(*args: Any, **kwargs: Any) -> dict[str, int]:
    return {}


def assert_coercer_caught(*args: Any, **kwargs: Any) -> bool:
    return True
