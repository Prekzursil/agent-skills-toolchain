#!/usr/bin/env python3
"""Independent syntactic counts via JS AST walk.

Counts CallExpressions by callee name. Does not interpret options objects,
nesting, background flags, or schema payloads. The adapter's semantic
extraction must match these counts or it is dropping nodes.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from jsparse import callee_name, is_filter_boolean, parse_js, walk

COUNT_KEYS = ("agent", "phase", "schema", "barrier")


def count_ast(ast: dict[str, Any]) -> dict[str, int]:
    agent = phase = schema = barrier = 0
    for node in walk(ast):
        if node.get("type") != "CallExpression":
            continue
        name = callee_name(node.get("callee"))
        if name == "agent":
            agent += 1
        elif name == "phase":
            phase += 1
        elif name == "schema":
            schema += 1
        elif is_filter_boolean(node):
            barrier += 1
    return {
        "agent": agent,
        "phase": phase,
        "schema": schema,
        "barrier": barrier,
    }


def count_source(src: str, filename: str) -> dict[str, int]:
    return count_ast(parse_js(src, filename))


def count_file(path: Path) -> dict[str, int]:
    src = path.read_text(encoding="utf-8")
    return count_source(src, path.name)
