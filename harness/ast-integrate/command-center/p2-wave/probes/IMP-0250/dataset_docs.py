#!/usr/bin/env python3
"""dataset-documentation: emit a dataset card from parsed schema + samples.

Stops (does not claim a stable schema) when column width is not uniform.
"""
from __future__ import annotations

from typing import Any

import extract_normalize as en
from data_quality import audit


def document(
    rows: list[list[bytes]],
    name: str = "extracted-table",
) -> dict[str, Any]:
    if not rows:
        return {
            "ok": False,
            "halt": "empty-table",
            "name": name,
            "columns": [],
            "row_count": 0,
        }
    header = [c.decode("utf-8", "replace") for c in rows[0]]
    body = rows[1:]
    widths = {len(r) for r in rows}
    if len(widths) != 1:
        return {
            "ok": False,
            "halt": "unstable-column-count",
            "name": name,
            "columns": header,
            "widths": sorted(widths),
            "row_count": len(body),
        }
    quality = audit(rows, expected_width=len(header), required=tuple(range(len(header))))
    samples = [
        [c.decode("utf-8", "replace") for c in row] for row in body[:5]
    ]
    return {
        "ok": True,
        "halt": None,
        "name": name,
        "columns": header,
        "row_count": len(body),
        "quality": quality,
        "samples": samples,
        "stopping_rules": {
            "max_stages": 3,
            "on_error": "halt",
            "unstable_schema": "halt",
        },
    }


def smoke() -> dict[str, Any]:
    planted = document(en.parse_table(en.planted_fixture()), name="planted")
    naive = document(en.parse_table_naive(en.planted_fixture()), name="naive-shift")
    ok = planted["ok"] is True and planted["columns"] == ["sku", "title", "qty"]
    halted = naive["ok"] is False and naive.get("halt") == "unstable-column-count"
    return {"ok": ok and halted, "planted_ok": planted["ok"], "naive_halt": naive.get("halt")}
