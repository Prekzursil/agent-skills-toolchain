"""TST-0329 conformance tests — twelve single-condition mutations.

Requires jsonschema (condition 4). Run:
  python3 -m pytest command-center/p2-wave/probes/TST-0329/test_conformance.py -q
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import ensure_jsonschema  # noqa: E402
import conformance as C  # noqa: E402

# Fail closed at collection time if jsonschema cannot be made available.
ensure_jsonschema.ensure()


@pytest.fixture
def battery(tmp_path: Path) -> dict:
    return C.run_battery(tmp_path)


def test_healthy_input_produces_true(battery: dict) -> None:
    assert battery["healthy"]["is_complete"] is True
    assert battery["healthy"]["verdict"] == "COMPLETE"
    assert battery["healthy"]["satisfied_count"] == 12


def test_twelve_mutations_each_false(battery: dict) -> None:
    assert battery["row_count"] == 12
    assert len(battery["rows"]) == 12
    for row in battery["rows"]:
        assert row["reducer_verdict"] == "FALSE", row
        assert row["is_complete"] is False, row
        assert row["verdict"] in {"INCOMPLETE", "INDETERMINATE"}


def test_condition_independence_exactly_one_unsatisfied(battery: dict) -> None:
    """Each mutant violates exactly one condition (UNSATISFIED); cascades are NOT-CHECKED."""
    assert battery["all_independent"] is True
    for row in battery["rows"]:
        assert row["unsatisfied"] == [row["condition"]], row
        assert row["not_checked"] == C.EXPECTED_CASCADE.get(row["condition"], []), row
        # Evaluating all twelve outcomes: only the target is UNSATISFIED.
        unsat_ns = [
            p["n"] for p in row["per_condition"] if p["outcome"] == "UNSATISFIED"
        ]
        assert unsat_ns == [row["condition"]], row["per_condition"]


def test_exit_code_zero_with_missing_artifact_is_row_two(battery: dict) -> None:
    """Catalog tests_required #4 / _USER-PROMPTS.md:10646."""
    row = next(r for r in battery["rows"] if r["condition"] == 2)
    assert row["is_10646_case"] is True
    assert row["exit_code_zero_present"] is True
    assert row["reducer_verdict"] == "FALSE"
    assert row["unsatisfied"] == [2]
    assert "exit_code=0" in row["mutation"]
    assert "missing" in row["mutation"] or "deleted" in row["mutation"]


def test_battery_ok_rollup(battery: dict) -> None:
    assert battery["ok"] is True
    assert battery["both_states"]["healthy_true"] is True
    assert battery["both_states"]["mutations_all_false"] is True


def test_measure_table_writes_twelve_rows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The measure script must emit a real 12-row table artifact (not a summary sentence)."""
    import measure_table as MT

    out_table = tmp_path / "twelve-row-table.json"
    out_md = tmp_path / "twelve-row-table.md"
    out_summary = tmp_path / "battery-summary.json"
    monkeypatch.setattr(MT, "OUT_TABLE", out_table)
    monkeypatch.setattr(MT, "OUT_MD", out_md)
    monkeypatch.setattr(MT, "OUT_SUMMARY", out_summary)
    assert MT.main() == 0
    table = json.loads(out_table.read_text(encoding="utf-8"))
    assert table["row_count"] == 12
    assert len(table["rows"]) == 12
    for i, row in enumerate(table["rows"], start=1):
        assert row["condition"] == i
        assert row["mutation"]
        assert row["reducer_verdict"] == "FALSE"
        assert row["condition_text"]
    md = out_md.read_text(encoding="utf-8")
    assert md.count("\n") >= 13  # header + separator + 12 rows
    assert "| 2 |" in md
    summary = json.loads(out_summary.read_text(encoding="utf-8"))
    assert summary["ok"] is True
    assert summary["case_10646_covered"] is True
