#!/usr/bin/env python3
"""Harvest quoted spans from claim/research artifacts on this worktree."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

PLANTED = HERE / "fixtures" / "planted-quotes.json"
PHASE3 = REPO / "command-center" / "phase3"
SKIP_NAMES = {"CNF-0164.json"}


def _walk(obj: Any, found: list[dict[str, Any]], origin: str) -> None:
    if isinstance(obj, dict):
        snippet = obj.get("snippet")
        path = obj.get("path")
        if isinstance(snippet, str) and snippet.strip() and isinstance(path, str) and path.strip():
            line = obj.get("line")
            anchor = obj.get("anchor")
            found.append(
                {
                    "id": f"CORPUS:{origin}:{len(found)+1}",
                    "quote": snippet,
                    "source_path": path.replace("\\", "/"),
                    "line": line if isinstance(line, int) else None,
                    "anchor": anchor if isinstance(anchor, str) else None,
                    "origin_artifact": origin,
                    "kind": "corpus",
                    "expect": None,
                    "note": "evidence.snippet presented as a quote of path",
                }
            )
        for v in obj.values():
            _walk(v, found, origin)
    elif isinstance(obj, list):
        for v in obj:
            _walk(v, found, origin)


def harvest_planted() -> list[dict[str, Any]]:
    rows = json.loads(PLANTED.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise SystemExit("planted-quotes.json must be a list")
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        out.append(
            {
                "id": str(row.get("id") or ""),
                "quote": str(row.get("quote") or ""),
                "source_path": str(row.get("source_path") or row.get("source_url") or ""),
                "line": None,
                "anchor": None,
                "origin_artifact": str(PLANTED.relative_to(REPO).as_posix()),
                "kind": str(row.get("kind") or "control"),
                "expect": row.get("expect"),
                "note": str(row.get("note") or ""),
            }
        )
    return out


def harvest_corpus() -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if not PHASE3.is_dir():
        return found
    for path in sorted(PHASE3.rglob("*.json")):
        if path.name in SKIP_NAMES:
            continue
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        origin = path.relative_to(REPO).as_posix()
        _walk(doc, found, origin)
    # Dedup by origin+source+quote
    seen: set[tuple[str, str, str]] = set()
    uniq: list[dict[str, Any]] = []
    for row in found:
        key = (row["origin_artifact"], row["source_path"], row["quote"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(row)
    return uniq


def harvest_all() -> list[dict[str, Any]]:
    return harvest_planted() + harvest_corpus()


def cases_from_receipt(doc: dict[str, Any]) -> list[dict[str, Any]]:
    """Read classified cases from either the domain payload or receipt_core extensions."""
    cases = doc.get("cases")
    if isinstance(cases, list) and cases:
        return [c for c in cases if isinstance(c, dict)]
    ext = doc.get("extensions")
    if isinstance(ext, dict):
        cases = ext.get("cases")
        if isinstance(cases, list):
            return [c for c in cases if isinstance(c, dict)]
    return []


def absent_cases_from_receipt(doc: dict[str, Any]) -> list[dict[str, Any]]:
    absents = doc.get("absent_cases")
    if isinstance(absents, list):
        return [c for c in absents if isinstance(c, dict)]
    ext = doc.get("extensions")
    if isinstance(ext, dict):
        absents = ext.get("absent_cases")
        if isinstance(absents, list):
            return [c for c in absents if isinstance(c, dict)]
    return []


def rechecked_absent_ids(doc: dict[str, Any]) -> list[str]:
    reviewer = doc.get("reviewer") if isinstance(doc.get("reviewer"), dict) else {}
    ids = reviewer.get("rechecked_absent_ids")
    if isinstance(ids, list) and ids:
        return [str(x) for x in ids]
    ext = doc.get("extensions") if isinstance(doc.get("extensions"), dict) else {}
    ids = ext.get("rechecked_absent_ids")
    if isinstance(ids, list):
        return [str(x) for x in ids]
    return []


def reviewer_disagreements(doc: dict[str, Any]) -> list:
    reviewer = doc.get("reviewer") if isinstance(doc.get("reviewer"), dict) else {}
    dis = reviewer.get("disagreements")
    if isinstance(dis, list):
        return dis
    ext = doc.get("extensions") if isinstance(doc.get("extensions"), dict) else {}
    dis = ext.get("disagreements")
    return dis if isinstance(dis, list) else []
