"""Blind observers: question + input paths + disk only. Never read sealed answers."""
from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

LEDGER_LIST_KEYS = ("claims", "entries", "records", "items")
TEST_LIST_KEYS = ("tests", "entries", "records", "items")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def observe_claim_ledger(repo: Path) -> dict[str, Any]:
    path = repo / "command-center" / "CLAIM-REGISTRY.json"
    exists = path.is_file() and path.stat().st_size > 0
    is_ledger = False
    if exists:
        try:
            doc = _load_json(path)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            doc = None
        if isinstance(doc, dict):
            for key in LEDGER_LIST_KEYS:
                val = doc.get(key)
                if isinstance(val, list) and len(val) > 0:
                    is_ledger = True
                    break
    return {"exists": exists, "is_claim_ledger": is_ledger}


def observe_test_registry(repo: Path) -> dict[str, Any]:
    path = repo / "command-center" / "TEST-REGISTRY.json"
    exists = path.is_file() and path.stat().st_size > 0
    is_reg = False
    if exists:
        try:
            doc = _load_json(path)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            doc = None
        if isinstance(doc, dict):
            for key in TEST_LIST_KEYS:
                val = doc.get(key)
                if isinstance(val, list) and len(val) > 0:
                    is_reg = True
                    break
    return {"exists": exists, "is_test_registry": is_reg}


def _assigned_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name):
                return target.id
        return None
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return node.target.id
    return None


def observe_twelve_conditions(repo: Path) -> dict[str, Any]:
    path = repo / "tools" / "command-center" / "completion_predicate.py"
    if not path.is_file():
        return {"condition_count": None}
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if _assigned_name(node) != "CONDITIONS":
            continue
        values = ast.literal_eval(node.value)
        return {"condition_count": len(values)}
    return {"condition_count": None}


def observe_res0063_engines(repo: Path, doc: dict | None = None) -> dict[str, Any]:
    if doc is None:
        path = repo / "command-center" / "research" / "RES-0063.json"
        doc = _load_json(path)
    engines: list[str] = []
    for row in doc.get("catalog_fit_tests") or []:
        if not isinstance(row, dict):
            continue
        engine = row.get("engine")
        if isinstance(engine, str) and engine and engine not in engines:
            engines.append(engine)
    return {"engines": engines}


def observe_res0108_calibration(repo: Path) -> dict[str, Any]:
    path = repo / "command-center" / "research" / "RES-0108.json"
    doc = _load_json(path)
    cal = doc.get("calibration") if isinstance(doc, dict) else None
    if not isinstance(cal, dict):
        return {"tier1_row_count": None, "tier3_scored_as_gem": None}
    return {
        "tier1_row_count": cal.get("tier1_row_count"),
        "tier3_scored_as_gem": cal.get("tier3_scored_as_gem"),
    }


OBSERVERS = {
    "HC-CLAIM-LEDGER": observe_claim_ledger,
    "HC-TEST-REGISTRY": observe_test_registry,
    "HC-TWELVE-CONDITIONS": observe_twelve_conditions,
    "NC-RES-0063-ENGINES": observe_res0063_engines,
    "NC-RES-0108-CALIBRATION": observe_res0108_calibration,
}


def observe(repo: Path, conclusion_id: str, **kwargs: Any) -> dict[str, Any]:
    fn = OBSERVERS[conclusion_id]
    return fn(repo, **kwargs) if kwargs else fn(repo)
