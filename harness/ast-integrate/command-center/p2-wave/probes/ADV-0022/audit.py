"""Static audit: is tool_permissions enforced at call time or metadata-only?"""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from common import IMP_RECEIPT, IMP_TEST, PLANTED_REL, PRODUCTION_ROOTS, REPO

GATE_FUNCS = frozenset(
    {
        "evaluate_request",
        "invoke",
        "check_permission",
        "enforce_permissions",
        "permission_gate",
    }
)
SIDE_EFFECT_FUNCS = frozenset(
    {
        "run",
        "Popen",
        "call",
        "check_call",
        "check_output",
        "urlopen",
        "urlretrieve",
        "socket",
        "create_connection",
        "open",
        "write_text",
        "write_bytes",
    }
)
SKIP_DIR_NAMES = frozenset(
    {".git", "__pycache__", "node_modules", "fixtures", "p2-wave"}
)


def _py_files(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    out: list[Path] = []
    for path in root.rglob("*.py"):
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        out.append(path)
    return sorted(out)


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def classify_source(text: str) -> dict[str, Any]:
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return {
            "parse_ok": False,
            "error": type(exc).__name__,
            "gate_calls": [],
            "side_effect_calls": [],
            "tool_permissions_mentions": 0,
            "call_time": False,
            "metadata_only_mentions": False,
        }
    gate_calls: list[str] = []
    side_calls: list[str] = []
    perms = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = ""
            if isinstance(func, ast.Name):
                name = func.id
            elif isinstance(func, ast.Attribute):
                name = func.attr
            if name in GATE_FUNCS:
                gate_calls.append(name)
            if name in SIDE_EFFECT_FUNCS:
                side_calls.append(name)
        if isinstance(node, ast.Name) and node.id == "tool_permissions":
            perms += 1
        if isinstance(node, ast.Constant) and node.value == "tool_permissions":
            perms += 1
        if isinstance(node, ast.Attribute) and node.attr == "tool_permissions":
            perms += 1
    # Same-function gate then side-effect is call-time.
    call_time = False
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        names: set[str] = set()
        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue
            func = child.func
            name = ""
            if isinstance(func, ast.Name):
                name = func.id
            elif isinstance(func, ast.Attribute):
                name = func.attr
            if name:
                names.add(name)
        if names & GATE_FUNCS and names & SIDE_EFFECT_FUNCS:
            call_time = True
            break
    return {
        "parse_ok": True,
        "gate_calls": sorted(set(gate_calls)),
        "side_effect_calls": sorted(set(side_calls)),
        "tool_permissions_mentions": perms,
        "call_time": call_time,
        "metadata_only_mentions": perms > 0 and not call_time,
    }


def scan_path(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    row = classify_source(text)
    row["path"] = _rel(path)
    return row


def measure() -> dict[str, Any]:
    production: list[dict[str, Any]] = []
    for rel in PRODUCTION_ROOTS:
        root = REPO / rel
        for path in _py_files(root):
            row = scan_path(path)
            if (
                row["call_time"]
                or row["gate_calls"]
                or row["tool_permissions_mentions"]
            ):
                production.append(row)
    planted = scan_path(REPO / PLANTED_REL)
    call_time_prod = [r for r in production if r["call_time"]]
    metadata_prod = [r for r in production if r["metadata_only_mentions"]]
    imp_receipt = (REPO / IMP_RECEIPT).is_file()
    imp_test = (REPO / IMP_TEST).is_file()
    metadata_only = (not call_time_prod) and (not imp_receipt) and (not imp_test)
    return {
        "production_call_time_files": [r["path"] for r in call_time_prod],
        "production_gate_files": [
            r["path"] for r in production if r["gate_calls"]
        ],
        "production_metadata_mentions": [r["path"] for r in metadata_prod],
        "planted": {
            "path": PLANTED_REL,
            "call_time": planted["call_time"],
            "gate_calls": planted["gate_calls"],
        },
        "imp_0059_receipt_present": imp_receipt,
        "imp_0059_test_present": imp_test,
        "metadata_only": metadata_only,
        "escaped_by_construction": metadata_only,
        "planted_detected": bool(planted["call_time"] and planted["gate_calls"]),
    }
