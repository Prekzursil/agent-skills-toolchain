#!/usr/bin/env python3
"""Measure TST-0329: emit the 12-row condition/mutation/verdict table.

Writes:
  twelve-row-table.json   — machine-readable evidence (required)
  twelve-row-table.md     — markdown table (human-readable twin)
  battery-summary.json    — both-states + independence rollup
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import conformance as C  # noqa: E402

OUT_TABLE = HERE / "twelve-row-table.json"
OUT_MD = HERE / "twelve-row-table.md"
OUT_SUMMARY = HERE / "battery-summary.json"


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tst0329-") as td:
        report = C.run_battery(Path(td))

    table = {
        "unit": "TST-0329",
        "title": "Shared completion predicate — one condition at a time",
        "evidence_requirement": (
            "Publish a 12-row table: condition, the mutation used, and the "
            "reducer verdict."
        ),
        "row_count": report["row_count"],
        "healthy_input_verdict": report["healthy"]["verdict"],
        "healthy_is_complete": report["healthy"]["is_complete"],
        "case_10646_row": 2,
        "rows": [
            {
                "condition": r["condition"],
                "condition_text": r["condition_text"],
                "mutation": r["mutation"],
                "reducer_verdict": r["reducer_verdict"],
                "verdict_enum": r["verdict"],
                "unsatisfied": r["unsatisfied"],
                "not_checked": r["not_checked"],
                "independent": r["independent"],
                "is_10646_case": r["is_10646_case"],
                "exit_code_zero_present": r["exit_code_zero_present"],
                "per_condition_outcomes": [
                    {"n": p["n"], "outcome": p["outcome"]} for p in r["per_condition"]
                ],
            }
            for r in report["rows"]
        ],
    }
    OUT_TABLE.write_text(json.dumps(table, indent=2) + "\n", encoding="utf-8")
    OUT_MD.write_text(C.table_markdown(report), encoding="utf-8")

    def _rel(p: Path) -> str:
        try:
            return str(p.resolve().relative_to(C.REPO.resolve()))
        except ValueError:
            return str(p)

    summary = {
        "unit": "TST-0329",
        "ok": report["ok"],
        "row_count": report["row_count"],
        "healthy_true": report["both_states"]["healthy_true"],
        "all_twelve_false": report["all_twelve_false"],
        "all_independent": report["all_independent"],
        "case_10646_covered": report["case_10646_covered"],
        "both_states": report["both_states"],
        "table_path": _rel(OUT_TABLE),
        "md_path": _rel(OUT_MD),
    }
    OUT_SUMMARY.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(summary, indent=2))
    print("--- twelve-row table ---")
    print(C.table_markdown(report), end="")
    if not report["ok"]:
        print("FAILED:TST-0329 battery ok=false", file=sys.stderr)
        return 1
    print("OK:TST-0329 twelve-row battery green (receipt still BLOCKED pending review)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
