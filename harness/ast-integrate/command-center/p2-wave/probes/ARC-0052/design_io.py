"""Read the A8 dossier payload from DESIGN.json.

Receipts that validate against architecture-dossier.schema.json keep domain
fields under report (receipt_core additionalProperties is false at the root).
Older drafts kept jobs / error_rewrites / samples at the root. Both shapes
are accepted so probes resume rather than scrap.
"""
from __future__ import annotations

from typing import Any


def payload(design: dict[str, Any]) -> dict[str, Any]:
    report = design.get("report")
    if isinstance(report, dict) and (
        report.get("kind") == "architecture-dossier"
        or "jobs" in report
        or "error_rewrites" in report
    ):
        return report
    return design


def jobs(design: dict[str, Any]) -> list[dict[str, Any]]:
    body = payload(design)
    rows = body.get("jobs")
    if isinstance(rows, list) and rows:
        return rows
    rows = design.get("jobs")
    return rows if isinstance(rows, list) else []


def error_rewrites(design: dict[str, Any]) -> list[dict[str, Any]]:
    body = payload(design)
    rows = body.get("error_rewrites")
    if isinstance(rows, list) and rows:
        return rows
    rows = design.get("error_rewrites")
    return rows if isinstance(rows, list) else []


def samples(design: dict[str, Any]) -> list[dict[str, Any]]:
    body = payload(design)
    rows = body.get("samples")
    if isinstance(rows, list) and rows:
        return rows
    rows = design.get("samples")
    return rows if isinstance(rows, list) else []
