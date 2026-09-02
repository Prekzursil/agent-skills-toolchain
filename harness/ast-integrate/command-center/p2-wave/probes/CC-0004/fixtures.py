#!/usr/bin/env python3
"""Scratch trees for CC-0004 detector controls.

Clean tree: one canonical reducer + one fan-in that imports it + documentary
mentions of a local artifact_delivered (strings/markdown only).
Planted trees add a real FunctionDef fork (function shape or class-method shape).
"""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

CANONICAL_SRC = '''"""Canonical shared completion reducer (CC-0003-shaped fixture)."""

def evaluate_completion(unit):
    path = unit.get("output_path") if isinstance(unit, dict) else None
    if not path:
        return False, "no-output-path"
    return True, "canonical-evaluate_completion"


def completion_verdict(unit):
    return evaluate_completion(unit)
'''

DISPATCHER_SRC = '''"""Legitimate fan-in: imports the shared reducer instead of rolling its own."""
from platform.lib.completion_predicate import evaluate_completion


def harvest_complete(unit):
    return evaluate_completion(unit)
'''

NOTES_SRC = '''"""Handbook entry (use-vs-mention control).

A fan-in that rolls its own completion check instead of importing
evaluate_completion is the CC-0004 failure class.

Do not paste this example:

    def artifact_delivered(unit):
        return Path(unit["output_path"]).exists()
"""

EXAMPLE = """
def artifact_delivered(unit):
    from pathlib import Path
    return Path(unit.get("output_path") or "").exists()
"""


def describe_defect():
    return "local artifact_delivered is a fork; import evaluate_completion"
'''

MARKDOWN_SRC = """# Fork defect (documentary mention)

Sites must import `evaluate_completion` from the shared reducer.

A local `def artifact_delivered(unit): return Path(p).exists()` is the
failure class this detector exists to find. This file is prose, not a
Python FunctionDef, so a semantic-role scan must stay silent here.
"""

PLANT_FUNCTION_SRC = '''"""Planted local completion predicate (known-broken function shape)."""
from pathlib import Path


def artifact_delivered(unit):
    path = unit.get("output_path") if isinstance(unit, dict) else None
    if not path:
        return False
    return Path(str(path)).exists()
'''

PLANT_METHOD_SRC = '''"""Planted local completion predicate (known-broken method shape)."""
from pathlib import Path


class Monitor:
    def unit_complete(self, unit):
        path = unit.get("output_path") if isinstance(unit, dict) else None
        if not path:
            return False
        return Path(str(path)).exists()
'''


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def def_lineno(path: Path, name: str) -> int:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return int(node.lineno)
    raise AssertionError(f"no FunctionDef {name!r} in {path}")


def write_clean_tree(root: Path) -> dict[str, Any]:
    root = Path(root)
    canonical = root / "platform" / "lib" / "completion_predicate.py"
    dispatcher = root / "tools" / "dispatcher.py"
    notes = root / "tools" / "notes.py"
    md = root / "docs" / "fork-defect.md"
    _write(canonical, CANONICAL_SRC)
    _write(dispatcher, DISPATCHER_SRC)
    _write(notes, NOTES_SRC)
    _write(md, MARKDOWN_SRC)
    return {
        "root": str(root),
        "canonical_rel": "platform/lib/completion_predicate.py",
        "canonical_line": def_lineno(canonical, "evaluate_completion"),
        "resolved_rel": "tools/dispatcher.py",
        "resolved_name": "harvest_complete",
        "resolved_line": def_lineno(dispatcher, "harvest_complete"),
        "mention_py": "tools/notes.py",
        "mention_md": "docs/fork-defect.md",
    }


def plant_function_fork(root: Path) -> dict[str, Any]:
    path = Path(root) / "tools" / "local_fork.py"
    _write(path, PLANT_FUNCTION_SRC)
    return {
        "plant_rel": "tools/local_fork.py",
        "plant_name": "artifact_delivered",
        "plant_line": def_lineno(path, "artifact_delivered"),
        "shape": "function",
    }


def plant_method_fork(root: Path) -> dict[str, Any]:
    path = Path(root) / "tools" / "monitor.py"
    _write(path, PLANT_METHOD_SRC)
    return {
        "plant_rel": "tools/monitor.py",
        "plant_name": "unit_complete",
        "plant_line": def_lineno(path, "unit_complete"),
        "shape": "method",
    }
