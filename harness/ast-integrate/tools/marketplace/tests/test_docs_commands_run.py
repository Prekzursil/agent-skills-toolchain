#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1].parent
sys.path.insert(0, str(TOOLS))
from marketplace.docs_commands import run_documented_commands  # noqa: E402

GOOD = Path(__file__).resolve().parents[1] / "fixtures" / "docs-parity-good"


def test_every_documented_command_executes() -> None:
    report = run_documented_commands(GOOD)
    assert report.ok, report.as_dict()
    assert len(report.results) >= 4


def test_broken_command_is_detected() -> None:
    report = run_documented_commands(GOOD)
    unknown = next(r for r in report.results if "--unknown" in r.invocation.argv_line)
    assert unknown.returncode == 2
    assert unknown.invocation.expected_exit == 2
