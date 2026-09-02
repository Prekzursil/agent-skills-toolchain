#!/usr/bin/env python3
"""Join structurally-unreadable paths to program claims (catalog fallback)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[4]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
CLAIM_REGISTRY = REPO / "command-center" / "CLAIM-REGISTRY.json"


def _unit_blob(unit: dict[str, Any]) -> str:
    parts = [
        str(unit.get("id") or ""),
        str(unit.get("title") or ""),
        str(unit.get("question_or_target") or ""),
        json.dumps(unit.get("inputs") or [], ensure_ascii=True),
        json.dumps(unit.get("output_path") or "", ensure_ascii=True),
    ]
    return "\n".join(parts)


def join_claims(unreadable_paths: list[str], *, sample_limit: int = 12) -> dict[str, Any]:
    registry_present = CLAIM_REGISTRY.is_file()
    registry_claims: list[dict[str, Any]] = []
    if registry_present:
        try:
            raw = json.loads(CLAIM_REGISTRY.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            registry_present = False
            registry_error = f"{type(exc).__name__}: {exc}"
            raw = None
        else:
            registry_error = None
            items = raw if isinstance(raw, list) else (raw.get("claims") or [])
            for item in items:
                if not isinstance(item, dict):
                    continue
                blob = json.dumps(item, ensure_ascii=True)
                hits = [p for p in unreadable_paths if p and p in blob]
                if hits:
                    registry_claims.append(
                        {
                            "id": item.get("id") or item.get("claim_id"),
                            "paths": hits,
                        }
                    )
    else:
        registry_error = "command-center/CLAIM-REGISTRY.json absent on this worktree"

    catalog_hits: dict[str, dict[str, Any]] = {}
    catalog_present = CATALOG.is_file()
    if catalog_present:
        data = json.loads(CATALOG.read_text(encoding="utf-8"))
        units = data.get("work_units") or []
        for unit in units:
            if not isinstance(unit, dict):
                continue
            blob = _unit_blob(unit)
            uid = str(unit.get("id") or "")
            for p in unreadable_paths:
                if not p:
                    continue
                if p not in blob and Path(p).name not in blob:
                    # catalog often cites the catalog itself by filename
                    continue
                if p not in blob and f"command-center/{Path(p).name}" not in blob:
                    if Path(p).name not in blob:
                        continue
                rec = catalog_hits.setdefault(
                    p,
                    {"path": p, "count": 0, "sample_ids": []},
                )
                rec["count"] += 1
                if uid and len(rec["sample_ids"]) < sample_limit:
                    rec["sample_ids"].append(uid)

    return {
        "claim_registry": {
            "path": "command-center/CLAIM-REGISTRY.json",
            "present": CLAIM_REGISTRY.is_file() and registry_present,
            "error": registry_error,
            "matching_claims": registry_claims[:50],
            "matching_count": len(registry_claims),
        },
        "catalog_path_cites": {
            "path": "command-center/WORK-UNIT-CATALOG.json",
            "present": catalog_present,
            "by_path": catalog_hits,
        },
        "method": (
            "CLAIM-REGISTRY.json if present; else WORK-UNIT-CATALOG.json "
            "units whose inputs/question cite the unreadable path"
        ),
    }
