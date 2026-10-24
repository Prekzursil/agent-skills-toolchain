"""IMP-0438: mutation battery is the test; M01 must stay caught after the fix."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import battery as B  # noqa: E402


@pytest.fixture(scope="module")
def armed():
    return B.run_battery(B.MUTATIONS, disarm=False)


def test_battery_size_is_sixteen():
    assert len(B.MUTATIONS) == 16


def test_armed_battery_catches_all_sixteen(armed):
    assert armed["n"] == 16
    assert armed["caught"] == 16
    assert armed["survivor_ids"] == []


def test_control_mutation_m01_still_caught(armed):
    m01 = next(r for r in armed["rows"] if r["id"] == "M01")
    assert m01["caught"] is True
    assert m01["claimed_check_in_output"] is True
    assert m01["exit_code"] != 0


def test_unmutated_control_exits_zero(armed):
    assert armed["control"]["exit_code"] == 0
    assert armed["control"]["success_marker"] is True


def test_historical_survivor_m16_closed_when_armed(armed):
    m16 = next(r for r in armed["rows"] if r["id"] == "M16")
    assert m16["historical_survivor"] is True
    assert m16["caught"] is True
    assert m16["exit_code"] != 0


def test_m16_also_caught_when_disarmed_via_v_defaults():
    """Honesty: IMP-0436 V-DEFAULTS closes M16 even under --no-require-complete."""
    soft = B.run_battery(
        [next(m for m in B.MUTATIONS if m["id"] == "M16")],
        disarm=True,
        include_control=False,
    )
    row = soft["rows"][0]
    assert row["caught"] is True
    assert row["exit_code"] != 0
    assert row["claimed_check_in_output"] is True


def test_known_m17_expansion_control_caught():
    report = B.run_battery([B.SEVENTEENTH], disarm=False, include_control=False)
    assert report["rows"][0]["caught"] is True
