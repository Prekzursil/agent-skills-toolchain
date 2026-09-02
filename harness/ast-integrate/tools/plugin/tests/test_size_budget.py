#!/usr/bin/env python3
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLUGIN = HERE.parent
if str(PLUGIN) not in sys.path:
    sys.path.insert(0, str(PLUGIN))

import fixtures as fx  # noqa: E402
from archive_census import DetectorFailure, census  # noqa: E402
from size_budget import (  # noqa: E402
    Budget,
    budget_copied_from_current,
    check_archive,
    derive_budget,
)


def test_over_budget_fails() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        previous = fx.previous_zip(tmp / "prev.zip")
        bloated = fx.over_budget_zip(tmp / "over.zip")
        budget = derive_budget(previous)
        bad = check_archive(bloated, budget)
        assert not bad["ok"], bad
        assert any(v.startswith("max_bytes:") for v in bad["violations"]), bad


def test_negative_control_raise_ceiling_goes_red() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        previous = fx.previous_zip(tmp / "prev.zip")
        bloated = fx.over_budget_zip(tmp / "over.zip")
        budget = derive_budget(previous)
        assert not check_archive(bloated, budget)["ok"]
        raised = Budget(
            max_bytes=bloated.stat().st_size + 1,
            max_file_count=10_000,
            derivation={"mutated": "ceiling-raised-above-fixture"},
        )
        assert check_archive(bloated, raised)["ok"]


def test_budget_derived_from_measurement_not_current() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        previous = fx.previous_zip(tmp / "prev.zip")
        current = fx.current_ok_zip(tmp / "curr.zip")
        budget = derive_budget(previous)
        assert budget.derivation["measured_archive_bytes"] == previous.stat().st_size
        assert not budget_copied_from_current(budget, current)


def test_dual_census_agrees_on_zip_and_tar() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        previous = fx.previous_zip(tmp / "prev.zip")
        tar_prev = fx.write_tar(tmp / "prev.tar", fx.PREVIOUS_FILES)
        z = census(previous)
        t = census(tar_prev)
        assert z["file_count"] == t["file_count"] == 4
        assert z["payload_bytes"] == t["payload_bytes"]
        assert z["independent"]["library"] != z["primary"]["library"]


def test_detector_failure_on_truncated_zip() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        previous = fx.previous_zip(tmp / "prev.zip")
        truncated = tmp / "truncated.zip"
        truncated.write_bytes(previous.read_bytes()[:40])
        try:
            census(truncated)
        except DetectorFailure:
            return
        raise AssertionError("truncated zip did not trip DetectorFailure")


if __name__ == "__main__":
    test_over_budget_fails()
    test_negative_control_raise_ceiling_goes_red()
    test_budget_derived_from_measurement_not_current()
    test_dual_census_agrees_on_zip_and_tar()
    test_detector_failure_on_truncated_zip()
    print("OK")
