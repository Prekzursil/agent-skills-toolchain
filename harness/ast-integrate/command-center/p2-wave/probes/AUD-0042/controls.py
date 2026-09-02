#!/usr/bin/env python3
"""Both-states control: collected=0 is never a pass; a live suite must collect >0."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import common as C  # noqa: E402

EMPTY = "command-center/p2-wave/probes/AUD-0042/fixtures/empty"
ONE = "command-center/p2-wave/probes/AUD-0042/fixtures/one"


def pytest_control_argv(target: str) -> list[str]:
    return C.pytest_argv(target) + ["--noconftest", "-o", "addopts="]


def run_required_tests() -> dict:
    code_empty, out_empty = C.run_cmd(pytest_control_argv(EMPTY), timeout=20)
    sum_empty = C.parse_summary(out_empty)
    code_one, out_one = C.run_cmd(pytest_control_argv(ONE), timeout=20)
    sum_one = C.parse_summary(out_one)
    fires = (
        sum_empty["collected"] == 0
        and not sum_empty["counted_as_test_success"]
        and not (code_empty == 0 and sum_empty["collected"] == 0 and sum_empty["counted_as_test_success"])
    )
    silent = sum_one["collected"] > 0 and sum_one["counted_as_test_success"] and code_one == 0
    return {
        "id": "AUD0042-C1-zero-collect-is-not-success",
        "fired_on_bad_state": fires,
        "silent_on_good_state": silent,
        "pass": bool(fires and silent),
        "bad": {
            "target": EMPTY,
            "exit_code": code_empty,
            "summary": sum_empty,
            "output_tail": out_empty[-800:],
        },
        "good": {
            "target": ONE,
            "exit_code": code_one,
            "summary": sum_one,
            "output_tail": out_one[-800:],
        },
    }
