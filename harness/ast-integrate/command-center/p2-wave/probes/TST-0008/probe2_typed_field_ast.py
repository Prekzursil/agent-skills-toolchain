#!/usr/bin/env python3
"""Probe 2: the checker reads a typed `status` field (AST), not free text.

Evidence requirement: the checker reading a typed field rather than
scanning free text. Both-states: a substring mutant of the same module
must SATISFY the body-mention fixture that the live checker rejects.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sentinel_check as C  # noqa: E402

SRC = HERE / "sentinel_check.py"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0008-probe2 {msg}")
    return 1


def _const_str(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    index_ty = getattr(ast, "Index", None)
    if index_ty is not None and isinstance(node, index_ty):
        return _const_str(node.value)
    return None


def fn_named(tree: ast.AST, name: str) -> ast.FunctionDef | None:
    for node in tree.body if isinstance(tree, ast.Module) else ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def reads_status_key(fn: ast.FunctionDef) -> list[str]:
    hits: list[str] = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Subscript) and _const_str(node.slice) == "status":
            hits.append("subscript:status")
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "get":
                if node.args and _const_str(node.args[0]) == "status":
                    hits.append("get:status")
            if isinstance(func, ast.Name) and func.id in {"hasattr"}:
                continue
    return hits


def expected_in_payload(fn: ast.FunctionDef, expected_arg: str = "expected") -> list[str]:
    """`expected in <payload>` / `expected not in <payload>` — substring scan."""
    hits: list[str] = []
    for node in ast.walk(fn):
        if not isinstance(node, ast.Compare):
            continue
        left = node.left
        if not (isinstance(left, ast.Name) and left.id == expected_arg):
            continue
        for op, _rhs in zip(node.ops, node.comparators):
            if isinstance(op, (ast.In, ast.NotIn)):
                hits.append(type(op).__name__)
    return hits


def dumps_calls(fn: ast.FunctionDef) -> int:
    n = 0
    for node in ast.walk(fn):
        if isinstance(node, ast.Attribute) and node.attr == "dumps":
            n += 1
        if isinstance(node, ast.Name) and node.id == "dumps":
            n += 1
    return n


def main() -> int:
    src = SRC.read_text(encoding="utf-8")
    tree = ast.parse(src)
    role_fn = fn_named(tree, "check_sentinel_role")
    term_fn = fn_named(tree, "status_terminal_line")
    sub_fn = fn_named(tree, "check_sentinel_substring")
    if role_fn is None or term_fn is None or sub_fn is None:
        return fail("missing check_sentinel_role / status_terminal_line / substring cousin")

    status_hits = reads_status_key(role_fn) + reads_status_key(term_fn)
    print(json.dumps({"status_field_reads": status_hits}, sort_keys=True))
    if not status_hits:
        return fail("neither role checker nor status_terminal_line reads key 'status'")

    role_in = expected_in_payload(role_fn) + expected_in_payload(term_fn)
    print(json.dumps({"role_expected_in_payload": role_in}, sort_keys=True))
    if role_in:
        return fail("role checker uses expected-in-payload substring membership")

    if dumps_calls(role_fn) or dumps_calls(term_fn):
        return fail("role checker dumps the document (free-text scan)")

    sub_in = expected_in_payload(sub_fn)
    print(json.dumps({"substring_cousin_in_ops": sub_in}, sort_keys=True))
    if not sub_in:
        return fail("substring cousin no longer uses expected in payload")

    body_path = HERE / "fixtures" / "body_mention.json"
    doc = C.load_receipt(body_path)
    text = body_path.read_text(encoding="utf-8")
    live = C.check_sentinel_role(doc, C.EXPECTED)
    mutant = C.check_sentinel_substring(text, C.EXPECTED)
    print(
        json.dumps(
            {
                "body_mention_live_satisfies": live["satisfies"],
                "body_mention_substring_satisfies": mutant["satisfies"],
                "live_reason": live["reason"],
            },
            sort_keys=True,
        )
    )
    if live["satisfies"] is True:
        return fail("live role checker accepted mention-only fixture")
    if mutant["satisfies"] is not True:
        return fail("substring mutant silent on mention-only fixture")
    if live["reason"] != "status-field-empty":
        return fail(f"expected status-field-empty, got {live['reason']}")

    print("SUCCESS:TST-0008-probe2 typed status field; substring mutant fires")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
