#!/usr/bin/env python3
"""AST order: production parse_record sanitizes before it splits."""
from __future__ import annotations

import ast
from pathlib import Path


def _call_name(node: ast.AST) -> str | None:
    if not isinstance(node, ast.Call):
        return None
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _fn(tree: ast.AST, name: str) -> ast.FunctionDef | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def _ordered_calls(fn: ast.FunctionDef) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    for node in ast.walk(fn):
        name = _call_name(node)
        if name:
            found.append((node.lineno, name))
    found.sort(key=lambda x: x[0])
    return found


def check_parse_order(source_path: Path) -> dict[str, object]:
    src = source_path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    prod = _fn(tree, "parse_record")
    naive = _fn(tree, "parse_record_naive")
    if prod is None or naive is None:
        return {"ok": False, "error": "parse_record or parse_record_naive missing"}
    prod_calls = [n for _, n in _ordered_calls(prod)]
    naive_calls = [n for _, n in _ordered_calls(naive)]
    try:
        prod_strip = prod_calls.index("strip_controls_except_delimiter")
        prod_split = prod_calls.index("split_fields")
    except ValueError:
        return {
            "ok": False,
            "error": "production parse_record missing strip or split_fields",
            "prod_calls": prod_calls,
        }
    try:
        naive_split = naive_calls.index("split_on_delimiter_and_controls")
        naive_strip = naive_calls.index("strip_controls_except_delimiter")
    except ValueError:
        return {
            "ok": False,
            "error": "naive parser missing split-then-strip pair",
            "naive_calls": naive_calls,
        }
    prod_ok = prod_strip < prod_split
    naive_ok = naive_split < naive_strip
    # Production must not call the naive splitter.
    prod_uses_naive = "split_on_delimiter_and_controls" in prod_calls
    return {
        "ok": prod_ok and naive_ok and not prod_uses_naive,
        "prod_strip_before_split": prod_ok,
        "naive_split_before_strip": naive_ok,
        "prod_avoids_naive_splitter": not prod_uses_naive,
        "prod_calls": prod_calls,
        "naive_calls": naive_calls,
    }
