"""Load the labelled IMP-0395 corpus (fusion+override traces + gold sets)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
LABELLED = FIXTURES / "labelled.json"
INDEX = FIXTURES / "index.json"


def load_index() -> dict[str, Any]:
    return json.loads(INDEX.read_text(encoding="utf-8"))


def load_labelled() -> dict[str, Any]:
    return json.loads(LABELLED.read_text(encoding="utf-8"))


def cases() -> list[dict[str, Any]]:
    doc = load_labelled()
    rows = doc.get("cases") or []
    if len(rows) < 3:
        raise SystemExit("FAILED:IMP-0395 labelled corpus has fewer than 3 cases")
    return rows


def case_to_trace(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "query_id": case["query_id"],
        "query": case["query"],
        "min_score": case["min_score"],
        "budget_tokens": case["budget_tokens"],
        "near_miss_margin": case.get("near_miss_margin", 0.20),
        "overrides": case.get("overrides") or {"banned": [], "pinned": []},
        "candidates": list(case["candidates"]),
    }


def index_ids(index: dict[str, Any] | None = None) -> set[str]:
    idx = index if index is not None else load_index()
    return {
        str(c.get("capability_id"))
        for c in (idx.get("capabilities") or [])
        if c.get("capability_id")
    }
