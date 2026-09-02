"""Hunt catalog-claimed corpus files and recount TRANSLATE if present."""
from __future__ import annotations

from pathlib import Path

BLUEPRINT_NAME = "09-WORKFLOW-BLUEPRINT-LIBRARY.json"
REGISTRY_NAME = "08-WORKFLOW-CANDIDATE-REGISTRY.json"


def _candidates(repo: Path, name: str) -> list[Path]:
    home = Path("/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806")
    return [
        home / name,
        Path("/c/Users/Prekzursil/.claude/harness-restore-20260806") / name,
        Path("C:/Users/Prekzursil/.claude/harness-restore-20260806") / name,
        repo / name,
        repo / "command-center" / "wfa" / name,
        repo / "command-center" / "foundry" / name,
        repo / "harness-restore-20260806" / name,
    ]


def _first_file(paths: list[Path]) -> Path | None:
    for p in paths:
        try:
            if p.is_file() and p.stat().st_size > 0:
                return p
        except OSError:
            continue
    return None


def recount_blueprints(data: dict) -> dict:
    rows = data.get("blueprints")
    if not isinstance(rows, list):
        rows = data.get("records") if isinstance(data.get("records"), list) else []
        if not rows and isinstance(data, list):
            rows = data
    total = len(rows) if isinstance(rows, list) else 0
    translate = 0
    sample_ids: list[str] = []
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            route = str(row.get("route") or row.get("disposition") or "")
            if route.upper() == "TRANSLATE":
                translate += 1
                sid = str(row.get("id") or "")
                if sid:
                    sample_ids.append(sid)
    return {
        "total": total,
        "route_translate": translate,
        "sample_ids": sample_ids[:8],
    }


def recount_candidates(data: dict) -> dict:
    rows = data.get("candidates")
    if not isinstance(rows, list):
        rows = data if isinstance(data, list) else []
    total = len(rows) if isinstance(rows, list) else 0
    translate = 0
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            cls = str(row.get("classification") or "")
            if cls.upper() == "TRANSLATE":
                translate += 1
    return {"total": total, "classification_translate": translate}


def hunt(repo: Path) -> dict:
    import json

    bp_path = _first_file(_candidates(repo, BLUEPRINT_NAME))
    cand_path = _first_file(_candidates(repo, REGISTRY_NAME))
    blueprints = {
        "catalog_claimed_total": 108,
        "catalog_claimed_route_translate": 1,
        "path": str(bp_path) if bp_path else None,
        "present": bool(bp_path),
        "live_recount": "ABSENT",
    }
    if bp_path:
        try:
            data = json.loads(bp_path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                data = {"blueprints": data}
            rec = recount_blueprints(data if isinstance(data, dict) else {})
            blueprints["live_recount"] = rec
            blueprints["bytes"] = bp_path.stat().st_size
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            blueprints["live_recount"] = f"UNPARSEABLE:{type(exc).__name__}"
    candidates = {
        "catalog_claimed_total": 284,
        "catalog_claimed_classification_translate": 0,
        "path": str(cand_path) if cand_path else None,
        "present": bool(cand_path),
        "live_recount": "ABSENT",
    }
    if cand_path:
        try:
            data = json.loads(cand_path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                data = {"candidates": data}
            rec = recount_candidates(data if isinstance(data, dict) else {})
            candidates["live_recount"] = rec
            candidates["bytes"] = cand_path.stat().st_size
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            candidates["live_recount"] = f"UNPARSEABLE:{type(exc).__name__}"
    return {"blueprints": blueprints, "candidates": candidates}
