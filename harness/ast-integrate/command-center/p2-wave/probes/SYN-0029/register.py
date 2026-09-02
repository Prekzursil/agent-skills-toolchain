#!/usr/bin/env python3
"""Load CC-0024's requirement register, or the nine named floors from the catalog.

CC-0024 EXTRACTS. This loader does not pretend a catalog quote is a full spec
extract: when the CC-0024 artifact is absent the register is the nine floors
CC-0024 is required to extract before any coverage number is reported, with
register_source recorded as a fallback.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
CC_0024 = REPO / "command-center" / "receipts" / "CC-0024.json"

NINE_FLOORS = (
    {
        "id": "REQ-FLOOR-2048-WORK-UNITS",
        "text": "at least 2048 work units",
        "floor": 2048,
    },
    {
        "id": "REQ-FLOOR-160-WORKFLOW-CANDIDATES",
        "text": "at least 160 workflow candidates",
        "floor": 160,
    },
    {
        "id": "REQ-FLOOR-096-BLUEPRINTS",
        "text": "at least 96 blueprints",
        "floor": 96,
    },
    {
        "id": "REQ-FLOOR-040-FLAGSHIP-WORKFLOWS",
        "text": "at least 40 flagship workflows",
        "floor": 40,
    },
    {
        "id": "REQ-FLOOR-048-COUNCIL-PROTOCOLS",
        "text": "at least 48 council protocols",
        "floor": 48,
    },
    {
        "id": "REQ-FLOOR-064-PRESETS",
        "text": "at least 64 presets",
        "floor": 64,
    },
    {
        "id": "REQ-FLOOR-100-BRAINSTORM-TARGETS",
        "text": "at least 100-idea brainstorm targets",
        "floor": 100,
    },
    {
        "id": "REQ-FLOOR-036-TEST-LAYERS",
        "text": "at least 36 test layers",
        "floor": 36,
    },
    {
        "id": "REQ-FLOOR-021-STOPPING-CONDITIONS",
        "text": "at least 21 stopping conditions",
        "floor": 21,
    },
)

CATALOG_ANCHOR = (
    "command-center/WORK-UNIT-CATALOG.json work_units[id=CC-0024]."
    "question_or_target (nine numeric floors that must be extracted before "
    "any coverage number is reported)"
)


def _catalog_unit(uid: str) -> dict | None:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    for unit in data.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == uid:
            return unit
    return None


def _record_from_obj(obj: dict) -> dict | None:
    rid = None
    for key in ("requirement_id", "id", "req_id", "floor_id"):
        val = obj.get(key)
        if isinstance(val, str) and val.strip():
            rid = val.strip()
            break
    text = None
    for key in ("text", "requirement_text", "requirement", "statement"):
        val = obj.get(key)
        if isinstance(val, str) and len(val.strip()) >= 8:
            text = val.strip()
            break
    if not rid or not text:
        return None
    anchor = None
    for key in ("spec_anchor", "anchor", "source", "spec_line"):
        val = obj.get(key)
        if isinstance(val, str) and val.strip():
            anchor = val.strip()
            break
    bound = obj.get("bound_unit_ids") or obj.get("bound_units") or obj.get("unit_ids")
    if not isinstance(bound, list):
        bound = []
    bound_ids = [str(x) for x in bound if isinstance(x, str) and x.strip()]
    kind = str(obj.get("kind") or "requirement")
    return {
        "requirement_id": rid,
        "text": text,
        "spec_anchor": anchor or "CC-0024 record (anchor unstated)",
        "bound_unit_ids": bound_ids,
        "kind": kind,
    }


def _walk_records(node: Any, out: list[dict], depth: int = 0) -> None:
    if depth > 6:
        return
    if isinstance(node, dict):
        rec = _record_from_obj(node)
        if rec is not None and any(
            k in node for k in ("spec_anchor", "requirement_text", "bound_unit_ids", "floor")
        ):
            out.append(rec)
            return
        for key in (
            "requirements",
            "records",
            "requirement_records",
            "floors",
            "numeric_floors",
            "items",
            "rows",
        ):
            if key in node:
                _walk_records(node[key], out, depth + 1)
    elif isinstance(node, list):
        for item in node:
            _walk_records(item, out, depth + 1)


def nine_floor_register() -> list[dict]:
    rows = []
    for floor in NINE_FLOORS:
        rows.append(
            {
                "requirement_id": floor["id"],
                "text": floor["text"],
                "spec_anchor": CATALOG_ANCHOR,
                "bound_unit_ids": [],
                "kind": "numeric-floor",
            }
        )
    return rows


def load_register() -> dict:
    cc_present = CC_0024.is_file() and CC_0024.stat().st_size > 0
    spec_path = REPO / "_USER-PROMPTS.md"
    spec_present = spec_path.is_file()
    source = "catalog-quoted-nine-floors"
    notes: list[str] = []
    records: list[dict] = []

    if cc_present:
        try:
            doc = json.loads(CC_0024.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            notes.append(f"CC-0024 unparseable: {type(exc).__name__}")
            doc = None
        if isinstance(doc, dict) and str(doc.get("state") or "").upper() in {
            "BLOCKED",
            "FAILED",
            "SEVERED",
            "TIMEOUT",
        }:
            notes.append(f"CC-0024 self-declared {doc.get('state')}")
            doc = None
        if doc is not None:
            found: list[dict] = []
            _walk_records(doc, found)
            # Dedup by id, first wins (zero retries).
            seen: set[str] = set()
            for rec in found:
                rid = rec["requirement_id"]
                if rid in seen:
                    continue
                seen.add(rid)
                records.append(rec)
            if records:
                source = "CC-0024.json"
            else:
                notes.append("CC-0024 present but no requirement records parsed")
    else:
        notes.append("command-center/receipts/CC-0024.json absent")

    if not records:
        records = nine_floor_register()
        notes.append(
            "fallback register is the nine named numeric floors quoted on CC-0024; "
            "full imperative extract from _USER-PROMPTS.md:10473-11437 is NOT-CHECKED"
        )

    if not spec_present:
        notes.append("_USER-PROMPTS.md absent on this worktree")

    unit = _catalog_unit("CC-0024")
    catalog_present = unit is not None
    return {
        "records": records,
        "source": source,
        "cc_0024_present": cc_present,
        "spec_present": spec_present,
        "catalog_cc_0024_present": catalog_present,
        "notes": notes,
        "path": (
            "command-center/receipts/CC-0024.json"
            if source == "CC-0024.json"
            else "command-center/WORK-UNIT-CATALOG.json"
        ),
    }
