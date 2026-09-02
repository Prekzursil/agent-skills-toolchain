"""Compare Python vs JS violation-id sets."""
from __future__ import annotations

from typing import Any


def compare(py: dict[str, list[str]], js: dict[str, list[str]]) -> list[dict[str, Any]]:
    fails = []
    keys = sorted(set(py) | set(js))
    for key in keys:
        a = set(py.get(key) or [])
        b = set(js.get(key) or [])
        if a != b:
            fails.append(
                {
                    "fixture": key,
                    "only_py": sorted(a - b),
                    "only_python": sorted(a - b),
                    "only_js": sorted(b - a),
                }
            )
    return fails
