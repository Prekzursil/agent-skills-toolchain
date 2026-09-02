#!/usr/bin/env python3
"""Load blueprint / protocol / preset records available on this worktree.

The Prompt-One libraries (09-WORKFLOW-BLUEPRINT-LIBRARY.json,
12-COUNCIL-PROTOCOLS-AND-PRESETS.json) are absent here. The live corpus is
the union of typed ARC-0010 registry rows of those kinds, CNL/WFA work-unit
title+question proxies (labelled as proxies), and planted mutants written
for this unit. Absence of the 96/48/64 libraries is recorded, not filled in.
"""
from __future__ import annotations

import json
from pathlib import Path

import planted

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
REGISTRY = REPO / "command-center" / "p2-wave" / "probes" / "ARC-0010" / "registry.json"

LIBRARY_CANDIDATES = (
    "09-WORKFLOW-BLUEPRINT-LIBRARY.json",
    "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
    "08-WORKFLOW-CANDIDATE-REGISTRY.json",
)
SEARCH_DIRS = (
    REPO,
    REPO / "command-center",
    REPO / "command-center" / "wfa",
    REPO / "command-center" / "design",
)

REGISTRY_KINDS = {
    "workflow_blueprint": "blueprint",
    "council_protocol": "protocol",
    "council_preset": "preset",
}


def _q(unit: dict) -> str:
    for key in (
        "question_or_target",
        "question_or_target",
        "question_or_target",
        "question_or_target",
        "title",
    ):
        val = unit.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def _kind_from_unit(uid: str, title: str, question: str) -> str | None:
    blob = f"{uid} {title} {question}".lower()
    if uid.startswith("CNL-"):
        if "preset" in blob:
            return "preset"
        return "protocol"
    if uid.startswith("WFA-") and "blueprint" in blob:
        return "blueprint"
    return None


def discover_libraries() -> dict[str, bool]:
    found: dict[str, bool] = {}
    for name in LIBRARY_CANDIDATES:
        found[name] = any((root / name).is_file() for root in SEARCH_DIRS)
    return found


def load_registry(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    doc = json.loads(path.read_text(encoding="utf-8"))
    rows = doc.get("entries") or doc.get("records") or []
    out: list[dict] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        kind = REGISTRY_KINDS.get(str(row.get("kind") or ""))
        if not kind:
            continue
        rid = str(row.get("id") or "").strip()
        if not rid:
            continue
        desc = str(row.get("description") or "")
        out.append(
            {
                "id": rid,
                "kind": kind,
                "family": "registry",
                "title": str(row.get("name") or rid),
                "body": desc or json.dumps(row, sort_keys=True, ensure_ascii=True),
                "source": str(path.relative_to(REPO)).replace("\\", "/"),
            }
        )
    return out


def load_proxies(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    doc = json.loads(path.read_text(encoding="utf-8"))
    units = doc.get("work_units") or []
    out: list[dict] = []
    for unit in units:
        if not isinstance(unit, dict):
            continue
        uid = str(unit.get("id") or "")
        title = str(unit.get("title") or "")
        question = _q(unit)
        kind = _kind_from_unit(uid, title, question)
        if not kind:
            continue
        out.append(
            {
                "id": f"proxy.{uid}",
                "kind": kind,
                "family": "work-unit-proxy",
                "title": title or uid,
                "body": question,
                "source": "command-center/WORK-UNIT-CATALOG.json",
                "proxy_of": uid,
            }
        )
    return out


def load_corpus() -> dict:
    libraries = discover_libraries()
    registry = load_registry(REGISTRY)
    proxies = load_proxies(CATALOG)
    plants = planted.records()
    by_id: dict[str, dict] = {}
    for rec in registry + proxies + plants:
        by_id[rec["id"]] = rec
    ordered = list(by_id.values())
    return {
        "libraries_present": libraries,
        "catalog_files_absent": [k for k, v in libraries.items() if not v],
        "counts": {
            "registry": len(registry),
            "proxies": len(proxies),
            "planted": len(plants),
            "scanned": len(ordered),
        },
        "records": ordered,
    }


load_corpus = load_corpus
