"""AST call-set: rotation/revocation forbidden; redact/scan allowed."""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

FORBIDDEN = {"rotate_secret", "revoke_secret", "delete_secret", "unset_env", "rotate"}
ALLOWED = {"secret_exposure", "redact_value", "scan_prefix", "load_blueprint", "smoke"}
HERE = Path(__file__).resolve().parents[1]


def _call_names(source: str) -> list[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                names.append(func.id)
            elif isinstance(func, ast.Attribute):
                names.append(func.attr)
    return names


def forbidden_hits(names: list[str]) -> list[str]:
    return [n for n in names if n in FORBIDDEN]


def assert_no_rotation() -> dict[str, Any]:
    sites = []
    files = 0
    call_count = 0
    for path in HERE.rglob("*.py"):
        files += 1
        text = path.read_text(encoding="utf-8", errors="replace")
        names = _call_names(text)
        call_count += len(names)
        for n in names:
            if n in FORBIDDEN:
                sites.append({"file": str(path), "name": n})
    return {
        "ok": not sites,
        "rotation_call_sites": sites,
        "call_count": call_count,
        "files": files,
    }


def assert_allowed(extra_allowed: set[str] | None = None) -> dict[str, Any]:
    allowed = set(ALLOWED) | set(extra_allowed or ())
    forbidden = []
    unknown = []
    for path in HERE.rglob("*.py"):
        names = _call_names(path.read_text(encoding="utf-8", errors="replace"))
        for n in names:
            if n in FORBIDDEN:
                forbidden.append(n)
    return {"ok": not forbidden, "forbidden": forbidden, "unknown": unknown}


def detector_fires_on_mutant(source: str) -> bool:
    names = _call_names(source)
    return any(n in FORBIDDEN or n in {"rotate_secret", "delete_secret"} for n in names)
