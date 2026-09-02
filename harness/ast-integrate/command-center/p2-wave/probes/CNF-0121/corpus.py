#!/usr/bin/env python3
"""Walk the live completion-receipt corpus for CNF-0121."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

EXCLUDE_REL = frozenset(
    {
        "command-center/confirmation/CNF-0121-reviewer-condition-audit.json",
        "command-center/p2-wave/probes/CNF-0121/SUBAGENT-RETURN.json",
        "command-center/p2-wave/probes/CNF-0121/UNIT-ARTIFACT-MANIFEST.json",
    }
)
_SKIP_NAMES = frozenset(
    {
        "ARTIFACT-MANIFEST.json",
        "UNIT-ARTIFACT-MANIFEST.json",
        "WORK-UNIT-CATALOG.json",
    }
)


def _is_receipt_shape(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    unit_id = value.get("unit_id") or value.get("id")
    if not isinstance(unit_id, str) or not unit_id.strip():
        return False
    if "reviewer" in value or "state" in value or "status" in value:
        return True
    artifacts = value.get("artifacts")
    return isinstance(artifacts, list) and bool(artifacts)


def load_catalog_units(repo: Path) -> dict[str, dict]:
    path = repo / "command-center" / "WORK-UNIT-CATALOG.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    for unit in data.get("work_units") or []:
        if isinstance(unit, dict) and isinstance(unit.get("id"), str):
            out[unit["id"]] = unit
    return out


def iter_receipt_files(repo: Path) -> list[Path]:
    roots = [
        repo / "command-center" / "receipts",
        repo / "command-center" / "confirmation",
        repo / "command-center" / "adversarial",
        repo / "command-center" / "audit",
        repo / "command-center" / "p2-wave" / "probes",
    ]
    found: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.json")):
            rel = path.relative_to(repo).as_posix()
            if rel in EXCLUDE_REL or path.name in _SKIP_NAMES:
                continue
            if any(part.startswith("_") for part in path.relative_to(root).parts):
                continue
            if root.name == "probes":
                if path.name != "SUBAGENT-RETURN.json":
                    continue
                if "CNF-0121" in path.parts:
                    continue
            found.append(path)
    return found


def load_receipts(repo: Path) -> tuple[list[tuple[str, dict]], list[dict]]:
    rows: list[tuple[str, dict]] = []
    errors: list[dict] = []
    for path in iter_receipt_files(repo):
        rel = path.relative_to(repo).as_posix()
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            errors.append({"path": rel, "error": f"{type(exc).__name__}: {exc}"})
            continue
        if not _is_receipt_shape(value):
            continue
        rows.append((rel, value))
    return rows, errors


def author_index(rows: list[tuple[str, dict]]) -> dict[str, list[str]]:
    from shared_reducer import author_identities

    index: dict[str, set[str]] = {}
    for _rel, receipt in rows:
        uid = str(receipt.get("unit_id") or receipt.get("id") or "")
        if not uid:
            continue
        index.setdefault(uid, set()).update(author_identities(receipt))
    return {uid: sorted(ids) for uid, ids in index.items()}


def context_for(receipt: dict, catalog: dict[str, dict], authors: dict[str, list[str]]) -> dict:
    uid = str(receipt.get("unit_id") or receipt.get("id") or "")
    deps = []
    unit = catalog.get(uid) or {}
    raw_deps = unit.get("dependencies") or []
    if isinstance(raw_deps, list):
        deps = [str(d) for d in raw_deps if isinstance(d, str)]
    planted = receipt.get("catalog_dependencies")
    if isinstance(planted, list) and planted:
        deps = [str(d) for d in planted]
    dep_authors = {dep: authors.get(dep, []) for dep in deps}
    return {"dependency_authors": dep_authors, "catalog_dependencies": deps}
