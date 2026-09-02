#!/usr/bin/env python3
"""Static enumeration of write call sites in the TST-0146 publisher modules."""
from __future__ import annotations

import ast
from pathlib import Path

HERE = Path(__file__).resolve().parent

PRODUCTION = ("atomic_publish", "child_atomic")
CONTROL = ("non_atomic_publish", "child_non_atomic")


def _qual(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parts: list[str] = []
        cur: ast.AST = node
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
        return ".".join(reversed(parts))
    return ""


def _open_mode(call: ast.Call) -> str | None:
    q = _qual(call.func)
    is_builtin = q == "open"
    is_method = q.endswith(".open")
    if not is_builtin and not is_method:
        return None
    # open(path, mode) vs Path.open(mode)
    idx = 1 if is_builtin else 0
    if len(call.args) > idx and isinstance(call.args[idx], ast.Constant):
        val = call.args[idx].value
        if isinstance(val, str):
            return val
    for kw in call.keywords:
        if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
            val = kw.value.value
            if isinstance(val, str):
                return val
    return None


def inspect_function(fn: ast.FunctionDef) -> dict:
    calls: list[str] = []
    open_modes: list[str] = []
    dest_inplace: list[str] = []
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        name = _qual(node.func)
        calls.append(name)
        mode = _open_mode(node)
        if mode is not None:
            open_modes.append(mode)
        # In-place dest writes: Path.write_bytes / dest.write_text, not tmp-report open().
        if name in {"write_bytes", "write_text"} or name.endswith(".write_bytes") or name.endswith(
            ".write_text"
        ):
            dest_inplace.append(name)
    has_replace = "os.replace" in calls or "os.rename" in calls
    has_tmp = any(c.endswith("mkstemp") or c.endswith("NamedTemporaryFile") for c in calls)
    dest_open_trunc = any(
        (m.startswith("w") or m.startswith("wb") or "w" in m.split("+")[0])
        and q_ok
        for m in open_modes
        for q_ok in [True]
    )
    # dest.open("wb") is the naive child tell; tmp-report uses builtin open().
    dest_open = any(c.endswith(".open") and not c.startswith("os.") for c in calls)
    inplace = bool(dest_inplace) or (dest_open and dest_open_trunc)
    if has_replace and has_tmp and not dest_inplace:
        klass = "ATOMIC"
    elif inplace and not has_replace:
        klass = "NON_ATOMIC"
    else:
        klass = "UNKNOWN"
    return {
        "name": fn.name,
        "class": klass,
        "calls": sorted(set(calls)),
        "open_modes": open_modes,
        "inplace_writes": dest_inplace,
        "has_replace": has_replace,
        "has_tmp": has_tmp,
        "has_replace": has_replace,
    }


def scan_file(path: Path) -> list[dict]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    rows = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            info = inspect_function(node)
            info["file"] = path.name
            rows.append(info)
    return rows


def scan_writers() -> dict:
    rows = scan_file(HERE / "writers.py")
    by_name = {r["name"]: r for r in rows}
    production = [by_name[n] for n in PRODUCTION if n in by_name]
    control = [by_name[n] for n in CONTROL if n in by_name]
    production_bad = [r for r in production if r["class"] != "ATOMIC"]
    control_hits = [r for r in control if r["class"] == "NON_ATOMIC"]
    all_atomic = len(production) == len(PRODUCTION) and not production_bad
    ctrl_ok = len(control_hits) == len(CONTROL)
    return {
        "file": "writers.py",
        "functions": rows,
        "production": production,
        "control": control,
        "production_all_atomic": all_atomic,
        "control_detected": ctrl_ok,
        "production_all_atomic": all_atomic,
        "control_detected": ctrl_ok,
        "production_bad": production_bad,
        "control_hits": control_hits,
    }


def scan_emit_receipt() -> dict:
    path = HERE / "emit_receipt.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    calls: list[str] = []
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            calls.append(_qual(node.func))
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imports.append(alias.name)
    uses_atomic = "atomic_publish" in calls or "atomic_publish" in imports
    inplace = any(c.endswith("write_text") or c.endswith("write_bytes") for c in calls)
    return {
        "file": "emit_receipt.py",
        "calls": sorted(set(calls)),
        "imports": sorted(set(imports)),
        "uses_atomic_publish": uses_atomic,
        "inplace_catalog_write": inplace,
        "ok": uses_atomic and not inplace,
    }


scan_writers = scan_writers
scan_emit_receipt = scan_emit_receipt
