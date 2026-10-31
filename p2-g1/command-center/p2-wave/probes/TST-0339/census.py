#!/usr/bin/env python3
"""TST-0339 default-argument exercise census engine.

For every function/method with default parameters, decide whether any TEST
call invokes it WITHOUT that argument:
  exercised    - at least one test call omits the parameter
  unexercised  - test calls exist but every one supplies the parameter
  no_test_calls- no test call references the function name at all
  unresolved   - the function name is ambiguous across product files, so the
                 call-site match cannot be attributed
Line coverage cannot see this hole; this census can.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path


def default_src(node) -> str:
    try:
        return ast.unparse(node)
    except Exception:
        return type(node).__name__


def call_name(call: ast.Call):
    f = call.func
    if isinstance(f, ast.Name):
        return f.id
    if isinstance(f, ast.Attribute):
        return f.attr
    return None


def scan_product_file(path: Path) -> list:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    rows = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        args = node.args
        pos = args.posonlyargs + args.args
        ndefaults = len(args.defaults)
        if ndefaults == 0:
            continue
        defaulted = pos[len(pos) - ndefaults:]
        for arg, d in zip(defaulted, args.defaults):
            rows.append({
                "file": path.as_posix(),
                "line": node.lineno,
                "anchor": f"{path.as_posix()}:{node.lineno}",
                "function": node.name,
                "param": arg.arg,
                "default": default_src(d),
            })
    return rows


def scan_test_calls(path: Path) -> list:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = call_name(node)
            if name:
                calls.append({
                    "name": name,
                    "n_positional": len([a for a in node.args if not isinstance(a, ast.Starred)]),
                    "keywords": [k.arg for k in node.keywords if k.arg],
                })
    return calls


def is_test_path(path: Path) -> bool:
    if path.name.startswith("test_") or path.name.endswith("_test.py"):
        return True
    return "tests" in path.parts


def _pos_index_of(row: dict) -> int:
    """Positional index a call must exceed to supply this param positionally."""
    path = Path(row["file"])
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == row["function"]:
            pos = node.args.posonlyargs + node.args.args
            for i, arg in enumerate(pos):
                if arg.arg == row["param"]:
                    return i
    return 10**6


def census(roots, exclude_parts=None):
    exclude_parts = exclude_parts or set()
    product_rows = []
    test_call_index = {}
    n_product = n_test = 0
    for root in roots:
        for path in root.rglob("*.py"):
            parts = set(path.parts)
            if (parts & exclude_parts) or "__pycache__" in path.parts or ".git" in path.parts:
                continue
            if is_test_path(path):
                n_test += 1
                for call in scan_test_calls(path):
                    test_call_index.setdefault(call["name"], []).append(call)
            else:
                n_product += 1
                product_rows.extend(scan_product_file(path))

    name_defs = {}
    for row in product_rows:
        key = row["function"] + ":" + row["param"]
        name_defs[key] = name_defs.get(key, 0) + 1

    exercised = unexercised = no_calls = unresolved = 0
    unex_rows, exercised_rows, unresolved_rows = [], [], []
    for row in product_rows:
        calls = test_call_index.get(row["function"], [])
        supplied = omitted = 0
        pidx = _pos_index_of(row)
        for call in calls:
            if row["param"] in call["keywords"]:
                supplied += 1
            elif call["n_positional"] > pidx:
                supplied += 1
            else:
                omitted += 1
        key = row["function"] + ":" + row["param"]
        if name_defs[key] > 1 and calls:
            unresolved += 1
            unresolved_rows.append(row)
        elif omitted:
            exercised += 1
            exercised_rows.append({**row, "calls_supplying": supplied, "calls_omitting": omitted})
        elif calls:
            unexercised += 1
            unex_rows.append({**row, "calls_supplying": supplied, "calls_omitting": omitted})
        else:
            no_calls += 1
    return {
        "n_defaults": len(product_rows),
        "n_exercised": exercised,
        "n_unexercised": unexercised,
        "n_no_test_calls": no_calls,
        "n_unresolved": unresolved,
        "unexercised": unex_rows,
        "exercised_rows": exercised_rows,
        "unresolved_rows": unresolved_rows,
        "product_files": n_product,
        "test_files": n_test,
    }


if __name__ == "__main__":
    import sys
    roots = [Path(a) for a in sys.argv[1:]]
    print(json.dumps(census(roots), indent=1))
