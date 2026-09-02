"""Classify benchmark calls as live vs hermetic."""
from __future__ import annotations

from typing import Any


def classify_calls(calls: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    rows = []
    for call in calls or []:
        url = str(call.get("url") or "")
        kind = "hermetic" if url.startswith("file:") or call.get("hermetic") else "live"
        rows.append({"call": call, "class": kind})
    return rows
