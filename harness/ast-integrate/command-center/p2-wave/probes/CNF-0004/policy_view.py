"""Merge report/extensions onto a confirmation-policy document for probes."""
from __future__ import annotations

from typing import Any


def fields(doc: dict[str, Any]) -> dict[str, Any]:
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    ext = doc.get("extensions") if isinstance(doc.get("extensions"), dict) else {}
    merged: dict[str, Any] = {}
    merged.update(ext)
    merged.update(report)
    for key in (
        "simulations",
        "threshold",
        "answer",
        "committed_at",
        "timestamp_proof",
        "expansion_bound",
        "state",
        "sentinel",
    ):
        if key in doc:
            merged[key] = doc[key]
    return merged
