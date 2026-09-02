#!/usr/bin/env python3
"""Load SYN-0041's five-way labelled report, or an honest empty report.

This unit joins; it does not generate the final report. A missing report is
an empty item set, so every register row is DISAPPEARED.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
REPORT = REPO / "command-center" / "synthesis" / "SYN-0041.final-report.json"
B11_NOTE = "work_units_meta.remeasured_2026_08_11.bucket_members.B11"


def _items_from(doc: Any) -> list[dict]:
    if isinstance(doc, list):
        return [x for x in doc if isinstance(x, dict)]
    if not isinstance(doc, dict):
        return []
    for key in ("items", "requirements", "claims", "rows", "labelled_items"):
        val = doc.get(key)
        if isinstance(val, list):
            return [x for x in val if isinstance(x, dict)]
    return []


def _b11_members() -> dict:
    payload = {
        "path": "command-center/WORK-UNIT-CATALOG.json",
        "field": B11_NOTE,
        "members": None,
        "present": False,
        "work_unit_count": None,
    }
    try:
        data = json.loads(CATALOG.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return payload
    if not isinstance(data, dict):
        return payload
    meta = data.get("work_units_meta")
    if not isinstance(meta, dict):
        return payload
    payload["work_unit_count"] = meta.get("work_unit_count")
    remeasured = meta.get("remeasured_2026_08_11")
    if not isinstance(remeasured, dict):
        return payload
    members = (remeasured.get("bucket_members") or {}).get("B11")
    payload["members"] = members
    payload["present"] = members is not None
    return payload


def load_report() -> dict:
    present = REPORT.is_file() and REPORT.stat().st_size > 0
    notes: list[str] = []
    items: list[dict] = []
    state = None
    if not present:
        notes.append("command-center/synthesis/SYN-0041.final-report.json absent")
    else:
        try:
            doc = json.loads(REPORT.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            notes.append(f"SYN-0041 unparseable: {type(exc).__name__}")
            doc = None
            present = False
        if isinstance(doc, dict):
            state = doc.get("state")
            if str(state or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
                notes.append(f"SYN-0041 self-declared {state}")
            items = _items_from(doc)
            if not items:
                notes.append("SYN-0041 present but no labelled items parsed")
        elif isinstance(doc, list):
            items = _items_from(doc)
    b11 = _b11_members()
    if b11.get("members") == 0:
        notes.append("Phase 13 bucket B11 has zero members on this catalog")
    return {
        "path": "command-center/synthesis/SYN-0041.final-report.json",
        "present": bool(present),
        "items": items,
        "state": state,
        "notes": notes,
        "b11": b11,
        "item_count": len(items),
    }
