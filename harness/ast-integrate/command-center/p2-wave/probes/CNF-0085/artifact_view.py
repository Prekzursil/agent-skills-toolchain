"""Helpers to read the comparison table out of a receipt or a legacy document."""
from __future__ import annotations

from typing import Any


def report_of(doc: dict[str, Any]) -> dict[str, Any]:
    report = doc.get("report")
    return report if isinstance(report, dict) else {}


def comparison_table(doc: dict[str, Any]) -> list[Any] | None:
    table = doc.get("comparison_table")
    if isinstance(table, list):
        return table
    table = report_of(doc).get("comparison_table")
    return table if isinstance(table, list) else None


def stub_control(doc: dict[str, Any]) -> dict[str, Any] | None:
    ctl = doc.get("always_true_stub_control")
    if isinstance(ctl, dict):
        return ctl
    ctl = report_of(doc).get("always_true_stub_control")
    return ctl if isinstance(ctl, dict) else None
