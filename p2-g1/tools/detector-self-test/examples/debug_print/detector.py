"""Worked-example detector: flag leftover debug ``print()`` calls in Python.

Wraps a real code-hygiene predicate (the estate's Python hooks warn about
stray ``print()`` in edited files). The both-states self-test proves this
detector FIRES on the ``broken/`` fixture (a module that left a ``print()`` in
the hot path) and stays SILENT on the ``fixed/`` fixture (which logs instead).
"""

from __future__ import annotations

import re
from pathlib import Path

_PRINT_CALL = re.compile(r"^\s*print\(")


def detect(target: Path) -> list[str]:
    """Return one finding per line that calls ``print(`` under ``target``."""
    findings: list[str] = []
    for path in sorted(target.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if _PRINT_CALL.match(line):
                findings.append(f"{path.name}:{lineno}: leftover debug print()")
    return findings
