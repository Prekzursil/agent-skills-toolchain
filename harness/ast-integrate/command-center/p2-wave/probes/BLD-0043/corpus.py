#!/usr/bin/env python3
"""Load CC-0024 requirement records and the B08 / TEST-REGISTRY test inventory."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from join import Requirement, TestRec, apply_registry, discover_tests, load_registry_maps

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
CC0024_RECEIPT = REPO / "command-center" / "receipts" / "CC-0024.json"
TEST_REGISTRY = REPO / "command-center" / "TEST-REGISTRY.json"
LIVE_TEST_DIR = "tools/command-center/tests"

# Nine numeric floors CC-0024 must extract before any coverage number.
# Tokens are what a reviewing read of the test body must actually assert.
FLOORS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("REQ-CC0024-F01", "at least 2048 work units", ("2048", "work unit")),
    (
        "REQ-CC0024-F02",
        "at least 160 workflow candidates/mechanisms",
        ("160", "workflow"),
    ),
    ("REQ-CC0024-F03", "at least 96 blueprints", ("96", "blueprint")),
    ("REQ-CC0024-F04", "at least 40 flagship workflows", ("40", "flagship")),
    ("REQ-CC0024-F05", "at least 48 council protocols", ("48", "protocol")),
    ("REQ-CC0024-F06", "at least 64 editable presets", ("64", "preset")),
    (
        "REQ-CC0024-F07",
        "100-unique-idea brainstorm target",
        ("100", "idea"),
    ),
    ("REQ-CC0024-F08", "36 test layers", ("36", "test layer")),
    ("REQ-CC0024-F09", "21 stopping conditions", ("21", "stopping")),
)


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def _catalog_cc0024() -> tuple[dict[str, Any] | None, int]:
    raw = CATALOG.read_text(encoding="utf-8")
    line_of_id = 0
    for i, line in enumerate(raw.splitlines(), 1):
        if '"id": "CC-0024"' in line or '"id":"CC-0024"' in line:
            line_of_id = i
            break
    doc = json.loads(raw)
    units = doc.get("work_units") or doc.get("items") or []
    for unit in units:
        if isinstance(unit, dict) and unit.get("id") == "CC-0024":
            return unit, line_of_id
    return None, line_of_id


def _records_from_cc0024_receipt(doc: Any) -> list[Requirement]:
    rows: list[Any] = []
    if isinstance(doc, dict):
        for key in ("requirements", "records", "requirement_records", "items"):
            if isinstance(doc.get(key), list):
                rows = doc[key]
                break
    elif isinstance(doc, list):
        rows = doc
    out: list[Requirement] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        rid = str(row.get("id") or row.get("req_id") or "")
        if not rid:
            continue
        if not rid.startswith("REQ-"):
            rid = f"REQ-{rid}"
        text = str(row.get("text") or row.get("statement") or row.get("title") or rid)
        src = str(
            row.get("source_path")
            or row.get("spec_path")
            or "command-center/receipts/CC-0024.json"
        )
        line = row.get("source_line") or row.get("line") or 1
        try:
            line_i = int(line)
        except (TypeError, ValueError):
            line_i = 1
        tokens = tuple(str(t) for t in (row.get("tokens") or []) if t)
        out.append(
            Requirement(
                id=rid,
                text=text,
                source_path=src,
                source_line=max(1, line_i),
                tokens=tokens,
            )
        )
    return out


def _floor_line(catalog_text: str, needle: str, fallback: int) -> int:
    for i, line in enumerate(catalog_text.splitlines(), 1):
        if needle in line and "CC-0024" in catalog_text[max(0, i - 400) : i + 400]:
            if re.search(r"2048|160 |96 |40 |48 |64 |100-|36 |21 ", line):
                return i
        if needle in line:
            return i
    return fallback


def live_requirements() -> tuple[list[Requirement], dict[str, Any]]:
    meta: dict[str, Any] = {
        "path": "command-center/receipts/CC-0024.json",
        "present": CC0024_RECEIPT.is_file(),
        "fallback": None,
    }
    receipt = _load_json(CC0024_RECEIPT) if CC0024_RECEIPT.is_file() else None
    from_receipt = _records_from_cc0024_receipt(receipt) if receipt is not None else []
    if from_receipt:
        meta["source"] = "cc0024-receipt"
        meta["count"] = len(from_receipt)
        return from_receipt, meta

    unit, id_line = _catalog_cc0024()
    catalog_text = CATALOG.read_text(encoding="utf-8")
    reqs: list[Requirement] = []
    for rid, text, tokens in FLOORS:
        needle = tokens[0]
        line = _floor_line(catalog_text, needle, id_line or 1)
        reqs.append(
            Requirement(
                id=rid,
                text=text,
                source_path="command-center/WORK-UNIT-CATALOG.json",
                source_line=line,
                tokens=tokens,
            )
        )
    if unit:
        question = str(unit.get("question_or_target") or "")
        for i, line in enumerate(CATALOG.read_text(encoding="utf-8").splitlines(), 1):
            if "nine numeric floors" in line or "2048 work units" in line:
                for req in reqs:
                    if req.source_line == (id_line or 1):
                        req.source_line = i
                break
        _ = question
    meta["source"] = "catalog-surrogate-cc0024-absent"
    meta["fallback"] = (
        "CC-0024 receipt absent and _USER-PROMPTS.md absent; extracted the "
        "nine named numeric floors from the CC-0024 catalog record"
    )
    meta["count"] = len(reqs)
    meta["catalog_id_line"] = id_line
    return reqs, meta


def live_tests() -> tuple[list[TestRec], dict[str, Any]]:
    tests = discover_tests(REPO, LIVE_TEST_DIR, corpus="live")
    registry_present = TEST_REGISTRY.is_file()
    mapping = load_registry_maps(TEST_REGISTRY) if registry_present else {}
    apply_registry(tests, mapping)
    meta = {
        "test_registry": {
            "path": "command-center/TEST-REGISTRY.json",
            "present": registry_present,
            "mapped_keys": len(mapping),
            "fallback": None
            if registry_present
            else "registry absent; join uses AST-discovered B08 inventory only",
        },
        "b08_inventory": {
            "method": "ast FunctionDef walk of tools/command-center/tests",
            "path": LIVE_TEST_DIR,
            "count": len(tests),
            "coverage_xml": False,
        },
    }
    return tests, meta


def fixture_requirements() -> list[Requirement]:
    path = HERE / "fixtures" / "reqs.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    out: list[Requirement] = []
    for row in doc["requirements"]:
        out.append(
            Requirement(
                id=row["id"],
                text=row["text"],
                source_path=row["source_path"],
                source_line=int(row["source_line"]),
                tokens=tuple(row.get("tokens") or []),
            )
        )
    return out


def fixture_tests() -> list[TestRec]:
    tests = discover_tests(
        REPO,
        "command-center/p2-wave/probes/BLD-0043/fixtures",
        corpus="fixture",
    )
    mapping = load_registry_maps(HERE / "fixtures" / "registry.json")
    apply_registry(tests, mapping)
    return tests
