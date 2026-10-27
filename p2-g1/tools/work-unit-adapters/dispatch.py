"""Dispatch the same catalog unit through Claude and Codex adapters (IMP-0422)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from claude import ClaudeAdapter
from codex import CodexAdapter


def load_catalog_unit(unit_id: str, repo: Path) -> dict[str, Any]:
    catalog = json.loads(
        (Path(repo) / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
    )
    for unit in catalog.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == unit_id:
            return unit
    raise KeyError(unit_id)


def dispatch_same_unit(
    unit_id: str, repo: Path | None = None, unit: dict[str, Any] | None = None
) -> dict[str, Any]:
    repo = Path(repo) if repo else Path(__file__).resolve().parents[2]
    unit = unit or load_catalog_unit(unit_id, repo)
    claude = ClaudeAdapter().dispatch(unit)
    codex = CodexAdapter().dispatch(unit)
    fields = []
    claude_by = {r["field"]: r for r in claude["leak_register"]}
    codex_by = {r["field"]: r for r in codex["leak_register"]}
    for field in unit:
        fields.append(
            {
                "field": field,
                "claude": claude_by[field],
                "codex": codex_by[field],
            }
        )
    return {
        "same_unit_both_adapters": True,
        "author_filled_columns": False,
        "generated_by": "adapter-runtime",
        "unit_id": unit_id,
        "dispatched_unit_id": unit_id,
        "claude": claude,
        "codex": codex,
        "fields": fields,
    }


__all__ = ["dispatch_same_unit", "load_catalog_unit"]
