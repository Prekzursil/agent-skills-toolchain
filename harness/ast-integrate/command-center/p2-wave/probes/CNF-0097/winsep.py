#!/usr/bin/env python3
"""Detect hardcoded Windows path separators in published payload files."""
from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

DRIVE = re.compile(r"(?i)(?:^|[^A-Za-z0-9_])[A-Za-z]:\\")
WIN_FRAG = re.compile(
    r"\\(?:Users|Windows|Program Files|AppData|System32)\\", re.IGNORECASE
)


def _snippet(src: str, lineno: int) -> str:
    lines = src.splitlines()
    if 1 <= lineno <= len(lines):
        return lines[lineno - 1].strip()[:200]
    return ""


def scan_python(src: str, rel: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    try:
        tree = ast.parse(src)
    except SyntaxError as exc:
        return [
            {
                "path": rel,
                "kind": "python-unparseable",
                "snippet": str(exc)[:200],
            }
        ]
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            val = node.value
            if DRIVE.search(val) or WIN_FRAG.search(val):
                findings.append(
                    {
                        "path": rel,
                        "kind": "windows-path-literal",
                        "snippet": _snippet(src, getattr(node, "lineno", 0) or 1),
                    }
                )
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr != "join":
                continue
            receiver = node.func.value
            if isinstance(receiver, ast.Constant) and receiver.value == "\\":
                findings.append(
                    {
                        "path": rel,
                        "kind": "backslash-join",
                        "snippet": _snippet(src, getattr(node, "lineno", 0) or 1),
                    }
                )
    return findings


def scan_text(src: str, rel: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for i, line in enumerate(src.splitlines(), 1):
        if DRIVE.search(line) or WIN_FRAG.search(line):
            findings.append(
                {
                    "path": rel,
                    "kind": "windows-path-text",
                    "snippet": line.strip()[:200],
                    "line": i,
                }
            )
    return findings


def scan_path(path: Path, rel: str) -> list[dict[str, Any]]:
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    if path.suffix == ".py":
        return scan_python(text, rel)
    if path.suffix in {".json", ".md", ".txt"}:
        return scan_text(text, rel)
    return []


def scan_tree(root: Path) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if "__pycache__" in rel.split("/"):
            continue
        findings.extend(scan_path(path, rel))
    return findings
