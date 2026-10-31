#!/usr/bin/env python3
"""Unit tests for the two-state harness itself (imported by IMP-0471 probe1)."""
from __future__ import annotations

import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[2]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from detectors.two_state import (  # noqa: E402
    VERDICT_DIFFERS,
    VERDICT_ERROR,
    VERDICT_IDENTICAL,
    VERDICT_NOT_CHECKED,
    VERDICT_SILENT_BOTH,
    harness_self_test,
    inert_stub,
    run_two_state,
)


def test_valid_control_is_differs() -> None:
    rec = run_two_state(lambda s: {"fired": s == "broken", "payload": s})
    assert rec.verdict == VERDICT_DIFFERS and rec.valid


def test_inert_stub_is_silent_both() -> None:
    rec = run_two_state(inert_stub)
    assert rec.verdict == VERDICT_SILENT_BOTH and not rec.valid


def test_always_fire_is_identical() -> None:
    rec = run_two_state(lambda _s: {"fired": True, "payload": "constant"})
    assert rec.verdict == VERDICT_IDENTICAL and not rec.valid


def test_missing_fixture_is_not_checked() -> None:
    rec = run_two_state(None)
    assert rec.verdict == VERDICT_NOT_CHECKED
    assert rec.good is None and rec.broken is None
    assert rec.has_known_broken_fixture is False


def test_raising_adapter_is_error() -> None:
    def boom(_state: str) -> dict:
        raise ValueError("adapter exploded")

    rec = run_two_state(boom)
    assert rec.verdict == VERDICT_ERROR and "adapter exploded" in rec.reason


def test_wrong_polarity_is_error() -> None:
    rec = run_two_state(lambda s: {"fired": s == "good", "payload": s})
    assert rec.verdict == VERDICT_ERROR and "polarity" in rec.reason


def test_self_test_passes() -> None:
    st = harness_self_test()
    assert st["pass"] is True
    assert st["two_state_valid"]["verdict"] == VERDICT_DIFFERS
    assert st["inert_stub"]["verdict"] == VERDICT_SILENT_BOTH
    assert st["always_fire"]["verdict"] == VERDICT_IDENTICAL
    assert st["missing_fixture"]["verdict"] == VERDICT_NOT_CHECKED


TESTS = (
    test_valid_control_is_differs,
    test_inert_stub_is_silent_both,
    test_always_fire_is_identical,
    test_missing_fixture_is_not_checked,
    test_raising_adapter_is_error,
    test_wrong_polarity_is_error,
    test_self_test_passes,
)


def run_all() -> dict:
    """Run every test; return a JSON-serializable summary (probe1 embeds it)."""
    results = []
    failed = 0
    for fn in TESTS:
        try:
            fn()
            results.append({"name": fn.__name__, "result": "PASS"})
        except AssertionError as exc:
            failed += 1
            results.append({"name": fn.__name__, "result": "FAIL", "detail": str(exc)})
    return {"n": len(TESTS), "failed": failed, "green": failed == 0, "tests": results}


def main() -> int:
    summary = run_all()
    for row in summary["tests"]:
        print(f"{row['result'].lower()} {row['name']}")
    print(f"{'SUCCESS' if summary['green'] else 'FAILED'}:test_two_state_harness {summary['n']} tests")
    return 0 if summary["green"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
