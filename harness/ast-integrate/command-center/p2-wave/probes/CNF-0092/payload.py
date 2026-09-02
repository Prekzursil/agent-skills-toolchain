"""Read confirmation payload from a council-audit receipt.

Domain fields live under report (receipt_core additionalProperties is false).
Older top-level keys are accepted so a re-read of a pre-schema artifact still
locates runs and anchors.
"""
from __future__ import annotations

from typing import Any


def report_of(doc: dict[str, Any]) -> dict[str, Any]:
    raw = doc.get("report")
    return raw if isinstance(raw, dict) else {}


def runs_of(doc: dict[str, Any]) -> list[dict[str, Any]]:
    rep = report_of(doc)
    items = rep.get("runs")
    if not isinstance(items, list):
        items = doc.get("runs")
    if not isinstance(items, list):
        return []
    return [row for row in items if isinstance(row, dict)]


def evidence_anchors_of(doc: dict[str, Any]) -> list[dict[str, Any]]:
    rep = report_of(doc)
    items = rep.get("evidence_anchors")
    if not isinstance(items, list):
        items = doc.get("evidence")
    if not isinstance(items, list):
        return []
    return [row for row in items if isinstance(row, dict)]
