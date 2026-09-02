#!/usr/bin/env python3
"""Coverage-table extractor that refuses to invent a number.

Absence of a coverage table is NOT-CHECKED, never 0 and never a pass.
Canned both-states inputs are the same ones already recorded in
control-not-checked-extractor.json.
"""
from __future__ import annotations

import re

# Istanbul / nyc "All files | 93.41 | ..." and coverage.py "TOTAL ... 90%"
COV_PAT = re.compile(
    r"(?:^TOTAL\s+(?:\d+\s+){2,}(?P<pytotal>\d+)%)"
    r"|(?:All files\s*\|\s*(?P<jslines>[\d.]+))",
    re.MULTILINE,
)

NO_COV_VITEST = (
    "> [email protected] test\n> vitest run\n\n"
    " Test Files  3 passed (3)\n      Tests  27 passed (27)\n"
)
ISTANBUL_TABLE = (
    "----------|---------|----------|---------|---------|\n"
    "File      | % Stmts | % Branch | % Funcs | % Lines |\n"
    "All files |   93.41 |    88.20 |   91.00 |   93.41 |\n"
)


def extract_coverage(text: str) -> tuple[str, str]:
    """Return (value, provenance). NEVER returns a number it did not find."""
    if not text:
        return "NOT-CHECKED", "no-output"
    m = COV_PAT.search(text)
    if not m:
        return "NOT-CHECKED", "no-coverage-table-in-output"
    val = m.group("pytotal") or m.group("jslines")
    return f"{val}%", "parsed-from-coverage-table"


def canned_control() -> dict:
    bad_val, bad_why = extract_coverage(NO_COV_VITEST)
    good_val, good_why = extract_coverage(ISTANBUL_TABLE)
    passed_looking, passed_why = extract_coverage(
        "tests passed\n27 passed (27)\n"
    )
    fires = bad_val == "NOT-CHECKED" and passed_looking == "NOT-CHECKED"
    silent = good_val != "NOT-CHECKED"
    return {
        "id": "AUD0051-C1",
        "bad_state_input": NO_COV_VITEST,
        "bad_state_result": [bad_val, bad_why],
        "good_state_input": ISTANBUL_TABLE,
        "good_state_result": [good_val, good_why],
        "passed_without_table_result": [passed_looking, passed_why],
        "fired_on_bad_state": fires,
        "silent_on_good_state": silent,
        "pass": bool(fires and silent),
    }
