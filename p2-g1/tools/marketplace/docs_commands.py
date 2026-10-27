"""Extract and execute documented command invocations."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class Invocation:
    argv_line: str
    expected_exit: int = 0

    @property
    def name(self) -> str:
        parts = self.argv_line.split()
        for tok in parts:
            if tok.endswith(".py"):
                return Path(tok).stem
        return parts[-1] if parts else ""


@dataclass
class RunRow:
    invocation: Invocation
    returncode: int

    @property
    def matched(self) -> bool:
        return self.returncode == self.invocation.expected_exit

    @property
    def ok(self) -> bool:
        return self.matched


@dataclass
class RunReport:
    results: list[RunRow]

    @property
    def ok(self) -> bool:
        return all(r.ok for r in self.results)

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "results": [
                {
                    "argv_line": r.invocation.argv_line,
                    "expected_exit": r.invocation.expected_exit,
                    "returncode": r.returncode,
                }
                for r in self.results
            ],
        }


def extract_documented_invocations(root: Path | str) -> list[Invocation]:
    root = Path(root)
    path = root / "docs" / "COMMANDS.md"
    if not path.is_file():
        path = root / "docs" / "SURFACE.md"
    rows: list[Invocation] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("$ "):
            stripped = stripped[2:]
        if stripped.startswith("python3 commands/") or stripped.startswith("python commands/"):
            expected = 2 if "--unknown" in stripped else 0
            rows.append(Invocation(stripped, expected))
    return rows


def run_documented_commands(root: Path | str) -> RunReport:
    root = Path(root)
    results: list[RunRow] = []
    for inv in extract_documented_invocations(root):
        proc = subprocess.run(
            inv.argv_line,
            cwd=str(root),
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        results.append(RunRow(inv, proc.returncode))
    return RunReport(results)
