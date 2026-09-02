"""Archaeology surface: load source-class indexes and the live WFA-0019 fixture."""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterator

from constants import (
    ANCHORS,
    CORPUS,
    SOURCE_CLASS_FILES,
    WFA0019_CLASS,
    WFA0019_CORPUS,
)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalise_record(raw: dict[str, Any], source_class: str, anchor_root: Path) -> dict[str, Any]:
    rec = deepcopy(raw)
    rec["source_class"] = rec.get("source_class") or source_class
    rec["mechanisms"] = [str(m) for m in (rec.get("mechanisms") or [])]
    rec["licence_class"] = rec.get("licence_class")
    rec["quality"] = float(rec.get("quality") or 0.0)
    rec["_anchor_root"] = str(anchor_root)
    if "provenance" not in rec or not isinstance(rec["provenance"], dict):
        rec["provenance"] = {}
    return rec


def iter_class(source_class: str) -> Iterator[dict[str, Any]]:
    if source_class == WFA0019_CLASS:
        yield from iter_wfa0019()
        return
    filename = SOURCE_CLASS_FILES.get(source_class)
    if not filename:
        return
    path = CORPUS / filename
    if not path.is_file():
        return
    doc = _load_json(path)
    for raw in doc.get("candidates") or []:
        if isinstance(raw, dict):
            yield _normalise_record(raw, source_class, ANCHORS)


def iter_wfa0019() -> Iterator[dict[str, Any]]:
    path = WFA0019_CORPUS / "08-WORKFLOW-CANDIDATE-REGISTRY.json"
    if not path.is_file():
        return
    doc = _load_json(path)
    for raw in doc.get("candidates") or []:
        if not isinstance(raw, dict):
            continue
        rec = _normalise_record(raw, WFA0019_CLASS, WFA0019_CORPUS)
        # WFA-0019 records have no licence_class; that is a real gap.
        rec["licence_class"] = rec.get("licence_class") or "UNKNOWN"
        rec["quality"] = float(rec.get("quality") or 0.35)
        rec["id"] = f"wfa0019:{rec.get('id')}"
        yield rec


def class_status(source_class: str) -> dict[str, Any]:
    if source_class == WFA0019_CLASS:
        path = WFA0019_CORPUS / "08-WORKFLOW-CANDIDATE-REGISTRY.json"
        n = sum(1 for _ in iter_wfa0019()) if path.is_file() else 0
        return {
            "source_class": source_class,
            "present": path.is_file(),
            "path": str(path) if path.is_file() else None,
            "n_candidates": n,
        }
    filename = SOURCE_CLASS_FILES.get(source_class)
    path = CORPUS / filename if filename else None
    present = bool(path and path.is_file())
    n = sum(1 for _ in iter_class(source_class)) if present else 0
    return {
        "source_class": source_class,
        "present": present,
        "path": str(path) if present else None,
        "n_candidates": n,
    }


def load_synonyms() -> dict[str, list[str]]:
    path = CORPUS / "mechanism_synonyms.json"
    if not path.is_file():
        return {}
    return _load_json(path)
