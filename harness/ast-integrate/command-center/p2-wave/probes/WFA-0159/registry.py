"""Load the 284-row candidate registry if present; otherwise the control corpus.

An absent authoritative registry is UNKNOWN, never 'still fine'.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from decay import ADOPT_CLASSES

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CONTROL = HERE / "fixtures" / "control_corpus.json"

AUTHORITATIVE_PATHS = [
    Path(
        "C:/Users/Prekzursil/.claude/harness-restore-20260806/"
        "08-WORKFLOW-CANDIDATE-REGISTRY.json"
    ),
    Path(
        "/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806/"
        "08-WORKFLOW-CANDIDATE-REGISTRY.json"
    ),
    Path(
        "/root/.claude/harness-restore-20260806/"
        "08-WORKFLOW-CANDIDATE-REGISTRY.json"
    ),
    REPO / "08-WORKFLOW-CANDIDATE-REGISTRY.json",
    REPO / "command-center" / "08-WORKFLOW-CANDIDATE-REGISTRY.json",
    REPO / "command-center" / "p2-wave" / "08-WORKFLOW-CANDIDATE-REGISTRY.json",
]

CATALOG_ADOPT_AS_IS = 122
CATALOG_ADOPT_WITH_WRAPPER = 20


def _load_json(path: Path) -> Optional[Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def first_existing(paths: list[Path]) -> Optional[Path]:
    for p in paths:
        if p.is_file() and p.stat().st_size > 0:
            return p
    return None


def load_control_corpus() -> dict:
    doc = _load_json(CONTROL)
    if not isinstance(doc, dict) or not isinstance(doc.get("candidates"), list):
        raise FileNotFoundError(f"control corpus missing: {CONTROL}")
    return doc


def load_authoritative() -> tuple[Optional[Path], Optional[dict]]:
    path = first_existing(AUTHORITATIVE_PATHS)
    if path is None:
        return None, None
    doc = _load_json(path)
    if not isinstance(doc, dict):
        return path, None
    return path, doc


def adopt_rows(candidates: list) -> list[dict]:
    rows = []
    for item in candidates:
        if isinstance(item, dict) and item.get("classification") in ADOPT_CLASSES:
            rows.append(item)
    return rows


def recount_adopt(candidates: list) -> dict:
    rows = adopt_rows(candidates)
    as_is = sum(1 for r in rows if r.get("classification") == "ADOPT-AS-IS")
    wrapper = sum(1 for r in rows if r.get("classification") == "ADOPT-WITH-WRAPPER")
    return {
        "adopt_class_total": len(rows),
        "adopt_as_is": as_is,
        "adopt_with_wrapper": wrapper,
        "recounted_from_array": True,
    }


def candidate_upstream_url(row: dict) -> Optional[str]:
    for key in ("upstream_url", "url", "origin"):
        val = row.get(key)
        if isinstance(val, str) and val.startswith("http"):
            return val
    prov = row.get("provenance")
    if isinstance(prov, str) and prov.startswith("http"):
        return prov
    if isinstance(prov, dict):
        for key in ("url", "repo", "github", "source"):
            val = prov.get(key)
            if isinstance(val, str) and val.startswith("http"):
                return val
    return None
