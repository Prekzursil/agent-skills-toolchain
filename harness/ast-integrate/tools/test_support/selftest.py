"""Calibration detectors: silent / always-on / discriminating."""
from __future__ import annotations

from typing import Any

from tools.test_support.both_states import run_both_states


def silent_detector(state: Any) -> bool:
    return False


def always_on_detector(state: Any) -> bool:
    return True


def discriminating_detector(state: Any) -> bool:
    if isinstance(state, dict):
        return bool(state.get("broken"))
    return bool(state)


def run_selftest() -> dict[str, Any]:
    silent = run_both_states(
        silent_detector, {"broken": False}, {"broken": True}, detector_id="selftest-silent"
    )
    always = run_both_states(
        always_on_detector,
        {"broken": False},
        {"broken": True},
        detector_id="selftest-always-on",
    )
    ok = run_both_states(
        discriminating_detector,
        {"broken": False},
        {"broken": True},
        detector_id="selftest-discriminating",
    )
    inverted = run_both_states(
        lambda state: not bool(isinstance(state, dict) and state.get("broken")),
        {"broken": False},
        {"broken": True},
        detector_id="selftest-inverted",
    )
    passed = (
        (not silent["valid"])
        and silent["reason"] == "silent-in-both"
        and (not always["valid"])
        and always["reason"] == "fires-in-both"
        and bool(ok["valid"])
        and (not inverted["valid"])
        and inverted["reason"] == "fires-on-good-silent-on-broken"
    )
    return {
        "pass": passed,
        "silent": silent,
        "always_on": always,
        "discriminating": {
            "known_good": ok["known_good"]["observation"],
            "known_broken": ok["known_broken"]["observation"],
            "valid": ok["valid"],
            "reason": ok["reason"],
        },
        "inverted": inverted,
        "silent_in_both_rejected": (not silent["valid"])
        and silent["reason"] == "silent-in-both",
        "always_on_rejected": (not always["valid"]) and always["reason"] == "fires-in-both",
        "inverted_rejected": (not inverted["valid"])
        and inverted["reason"] == "fires-on-good-silent-on-broken",
        "discriminating_accepted": bool(ok["valid"]),
    }
