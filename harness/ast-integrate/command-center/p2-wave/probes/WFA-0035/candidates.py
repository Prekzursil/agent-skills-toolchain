#!/usr/bin/env python3
"""Load WFA-0035 candidates from the live registry (if present) plus on-tree and planted fixtures.

The catalog names 08-WORKFLOW-CANDIDATE-REGISTRY.json (284 rows). That file is
not on this Linux worktree. Absence is recorded; 284 rows are not invented.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLANTED = HERE / "fixtures" / "planted_candidates.json"
ON_TREE_SPEC = HERE / "fixtures" / "on_tree_sources.json"

REGISTRY_PATHS = [
    REPO / "08-WORKFLOW-CANDIDATE-REGISTRY.json",
    REPO / "command-center" / "08-WORKFLOW-CANDIDATE-REGISTRY.json",
    REPO / "command-center" / "sources" / "08-WORKFLOW-CANDIDATE-REGISTRY.json",
    REPO / "command-center" / "wfa" / "08-WORKFLOW-CANDIDATE-REGISTRY.json",
    Path.home() / ".claude" / "harness-restore-20260806" / "08-WORKFLOW-CANDIDATE-REGISTRY.json",
    Path("/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json"),
]


def _first_docstring(text: str) -> str:
    m = re.search(r'"""(.*?)"""', text, re.DOTALL)
    if not m:
        m = re.search(r"'''(.*?)'''", text, re.DOTALL)
    if not m:
        raise RuntimeError("no module docstring")
    body = m.group(1).strip()
    para = body.split("\n\n", 1)[0]
    return " ".join(line.strip() for line in para.splitlines() if line.strip())


def _json_walk(doc: Any, path: str) -> Any:
    cur = doc
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur[part]
        else:
            raise RuntimeError(f"json walk failed at {part}")
    return cur


def load_on_tree() -> tuple[list[dict[str, Any]], list[str]]:
    spec = json.loads(ON_TREE_SPEC.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    missing: list[str] = []
    for item in spec["sources"]:
        rel = item["path"]
        path = REPO / rel
        if not path.is_file():
            missing.append(rel)
            continue
        raw = path.read_text(encoding="utf-8")
        kind = item["kind"]
        if kind == "docstring":
            does = _first_docstring(raw)
        elif kind == "json_field":
            doc = json.loads(raw)
            val = _json_walk(doc, item["json_path"])
            if isinstance(val, dict):
                does = json.dumps(val, ensure_ascii=True)
            else:
                does = str(val)
        else:
            raise RuntimeError(f"unknown kind {kind}")
        needle = item.get("must_contain")
        if needle and needle not in does and needle not in raw:
            raise RuntimeError(f"{rel}: must_contain not found: {needle!r}")
        if len(does) < 40:
            raise RuntimeError(f"{rel}: extracted does too short")
        rows.append(
            {
                "id": item["id"],
                "name": item.get("name") or item["id"],
                "does": does,
                "origin": rel,
                "family_origin": "on-tree",
                "planted": False,
                "expected_classes": item.get("expected_classes") or [],
                "source_sha_scope": rel,
            }
        )
    return rows, missing


def load_planted() -> list[dict[str, Any]]:
    doc = json.loads(PLANTED.read_text(encoding="utf-8"))
    rows = []
    for item in doc["candidates"]:
        rows.append(
            {
                "id": item["id"],
                "name": item.get("name") or item["id"],
                "does": item["does"],
                "origin": "fixtures/planted_candidates.json",
                "family_origin": "planted",
                "planted": True,
                "expected_classes": list(item.get("expected_classes") or []),
                "role": item.get("role") or "in-class",
            }
        )
    return rows


def inspect_registry() -> dict[str, Any]:
    hits = []
    for path in REGISTRY_PATHS:
        exists = path.is_file()
        hits.append(
            {
                "path": str(path),
                "exists": exists,
                "bytes": path.stat().st_size if exists else 0,
            }
        )
        if exists:
            doc = json.loads(path.read_text(encoding="utf-8"))
            cands = doc.get("candidates") if isinstance(doc, dict) else None
            n = len(cands) if isinstance(cands, list) else 0
            return {
                "present": True,
                "path": str(path),
                "n": n,
                "hits": hits,
                "candidates": cands if isinstance(cands, list) else [],
            }
    return {"present": False, "path": None, "n": 0, "hits": hits, "candidates": []}


def registry_as_candidates(reg: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for rec in reg.get("candidates") or []:
        if not isinstance(rec, dict):
            continue
        cid = str(rec.get("id") or rec.get("name") or "")
        does = str(rec.get("does") or rec.get("description") or "")
        if not cid or len(does) < 20:
            continue
        rows.append(
            {
                "id": cid,
                "name": str(rec.get("name") or cid),
                "does": does,
                "origin": "08-WORKFLOW-CANDIDATE-REGISTRY.json",
                "family_origin": str(rec.get("family") or "registry"),
                "planted": False,
                "expected_classes": [],
            }
        )
    return rows


def load_candidates() -> dict[str, Any]:
    reg = inspect_registry()
    planted = load_planted()
    on_tree, missing_on_tree = load_on_tree()
    registry_rows = registry_as_candidates(reg) if reg["present"] else []
    rows = planted + on_tree + registry_rows
    seen: set[str] = set()
    uniq = []
    for r in rows:
        if r["id"] in seen:
            continue
        seen.add(r["id"])
        uniq.append(r)
    return {
        "registry": {k: v for k, v in reg.items() if k != "candidates"},
        "n": len(uniq),
        "n_planted": sum(1 for r in uniq if r.get("planted")),
        "n_on_tree": sum(1 for r in uniq if r.get("family_origin") == "on-tree"),
        "n_registry": len(registry_rows),
        "n_missing_on_tree": len(missing_on_tree),
        "missing_on_tree": missing_on_tree,
        "candidates": uniq,
        "note": (
            "284-row Windows registry is absent"
            if not reg["present"]
            else f"live registry n={len(registry_rows)}"
        ),
    }


if __name__ == "__main__":
    pack = load_candidates()
    print(
        json.dumps(
            {
                "n": pack["n"],
                "n_planted": pack["n_planted"],
                "n_on_tree": pack["n_on_tree"],
                "n_registry": pack["n_registry"],
                "registry_present": pack["registry"]["present"],
            },
            indent=2,
        )
    )
