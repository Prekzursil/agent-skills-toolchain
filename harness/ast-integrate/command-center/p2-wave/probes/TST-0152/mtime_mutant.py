"""Known-broken mutant: stall from artifact mtime age alone.

This is the statusline defect (11-hour-finished agent rendered as a live stall).
The live classifier must NOT match this mutant on the finished fixture.
"""
from __future__ import annotations

from typing import Any, Mapping

ELEVEN_H_S = 11 * 3600


def classify_mtime_only(rec: Mapping[str, Any]) -> dict[str, Any]:
    age = rec.get("artifact_mtime_age_s") or 0
    try:
        age_n = float(age)
    except (TypeError, ValueError):
        age_n = 0.0
    stalled = age_n >= ELEVEN_H_S
    return {
        "id": str(rec.get("id") or "unknown"),
        "state": "stalled" if stalled else "active",
        "source": "file_mtime",
        "stall_from_mtime_only": stalled,
        "mtime_used_as_predicate": True,
    }
