"""Conformance checks independent of the SPDX linter (IMP-0116)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Violation:
    check: str
    detail: str = ""


@dataclass
class ConformanceReport:
    ok: bool
    violations: list[Violation]


def check_conformance(path: Path | str) -> ConformanceReport:
    root = Path(path)
    violations: list[Violation] = []
    readme = root / "README.md"
    if not readme.is_file():
        violations.append(Violation("readme-usage", "README.md missing"))
    else:
        text = readme.read_text(encoding="utf-8")
        if "## Usage" not in text:
            violations.append(Violation("readme-usage", "README.md missing ## Usage"))
    return ConformanceReport(ok=not violations, violations=violations)
