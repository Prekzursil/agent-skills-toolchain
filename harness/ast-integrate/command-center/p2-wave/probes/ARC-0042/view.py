"""Read migration-plan domain fields from a receipt-shaped or legacy artifact."""
from __future__ import annotations

from typing import Any, Mapping


def plan(doc: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(doc, dict):
        return {}
    rpt = doc.get("report")
    if isinstance(rpt, dict) and rpt.get("kind") == "migration-plan":
        return dict(rpt)
    return dict(doc)
