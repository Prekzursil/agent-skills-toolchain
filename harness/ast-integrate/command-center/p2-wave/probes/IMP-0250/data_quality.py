#!/usr/bin/env python3
"""data-quality-audit: flag column-count drift and empty required cells.

Runs on already-normalized rows AND on a naive parse of the same bytes so
a shift that only the broken parser produces is a named quality finding.
"""
from __future__ import annotations

from typing import Any

import extract_normalize as en


def audit(
    rows: list[list[bytes]],
    expected_width: int,
    required: tuple[int, ...] = (),
) -> dict[str, Any]:
    drift: list[dict[str, int]] = []
    empty_required: list[dict[str, int]] = []
    for i, row in enumerate(rows):
        if len(row) != expected_width:
            drift.append({"row": i, "width": len(row), "expected": expected_width})
        for col in required:
            if col < 0 or col >= len(row) or row[col] == b"":
                empty_required.append({"row": i, "col": col})
    return {
        "ok": not drift and not empty_required,
        "expected_width": expected_width,
        "column_drift": drift,
        "empty_required": empty_required,
        "row_count": len(rows),
    }


def audit_raw(raw: bytes, expected_width: int) -> dict[str, Any]:
    """Audit both parsers. Naive drift is expected on the planted fixture."""
    fixed = audit(en.parse_table(raw), expected_width)
    naive = audit(en.parse_table_naive(raw), expected_width)
    return {
        "fixed": fixed,
        "naive": naive,
        "naive_drift_only": (not fixed["column_drift"]) and bool(naive["column_drift"]),
    }


def smoke() -> dict[str, Any]:
    planted = en.planted_fixture()
    benign = en.benign_fixture()
    planted_r = audit_raw(planted, 3)
    benign_r = audit_raw(benign, 3)
    ok = (
        planted_r["naive_drift_only"] is True
        and planted_r["fixed"]["ok"] is True
        and benign_r["fixed"]["ok"] is True
        and benign_r["naive"]["ok"] is True
    )
    return {"ok": ok, "planted": planted_r, "benign": benign_r}
