"""Read domain fields from a receipt_core document or a legacy top-level shape."""
from __future__ import annotations

from typing import Any


def report_body(doc: dict[str, Any]) -> dict[str, Any]:
    report = doc.get("report")
    if isinstance(report, dict):
        return report
    ext = doc.get("extensions")
    if isinstance(ext, dict):
        return ext
    return doc


def sample_rows(doc: dict[str, Any]) -> list[dict[str, Any]]:
    for src in (report_body(doc), doc):
        rows = src.get("sample") if isinstance(src, dict) else None
        if isinstance(rows, list):
            return [r for r in rows if isinstance(r, dict)]
    return []


def named_test(doc: dict[str, Any], key: str) -> dict[str, Any]:
    body = report_body(doc)
    for blob in (body.get("tests"), doc.get("tests")):
        if isinstance(blob, dict) and isinstance(blob.get(key), dict):
            return blob[key]
    return {}
