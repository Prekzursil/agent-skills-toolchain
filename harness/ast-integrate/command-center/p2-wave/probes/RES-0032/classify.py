#!/usr/bin/env python3
"""Hosted-agent adapter-targetability classifier for RES-0032."""
from __future__ import annotations

from collections import Counter
from typing import Any

ALLOWED = ("public-versioned-API", "private-API", "UI-only")


def histogram(rows: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(str(r.get("verdict") or "") for r in rows))


def control_ui_only_and_discriminating(rows: list[dict[str, Any]]) -> tuple[bool, str]:
    if not rows:
        return False, "empty-table"
    verdicts = [str(r.get("verdict") or "") for r in rows]
    unknown = [v for v in verdicts if v not in ALLOWED]
    if unknown:
        return False, f"unknown-class:{unknown[0]}"
    ui = sum(1 for v in verdicts if v == "UI-only")
    distinct = {v for v in verdicts if v}
    if ui < 1:
        return False, "no-UI-only-row"
    if len(distinct) < 2:
        return False, "classifier-not-discriminating"
    return True, f"ui_only={ui} classes={sorted(distinct)}"


def citations_complete(rows: list[dict[str, Any]]) -> tuple[bool, str]:
    for i, row in enumerate(rows):
        cit = row.get("citation")
        if not isinstance(cit, dict):
            return False, f"row[{i}] missing citation object"
        url = str(cit.get("url") or "").strip()
        fetched = str(cit.get("fetched_at") or "").strip()
        sha = str(cit.get("sha256") or "").strip()
        status = cit.get("http_status")
        pin = str(row.get("version_or_commit") or cit.get("version_or_commit") or "").strip()
        if not url.startswith("http"):
            return False, f"row[{i}] citation url missing"
        if len(fetched) < 10:
            return False, f"row[{i}] fetch timestamp missing"
        if not isinstance(status, int) or status < 200 or status >= 400:
            return False, f"row[{i}] http_status not a successful fetch"
        if len(sha) != 64:
            return False, f"row[{i}] sha256 missing"
        if not pin:
            return False, f"row[{i}] unversioned claim"
    return True, f"citations={len(rows)}"
