"""Pre-dispatch policy: no fire-and-forget on an awaited unit, no implicit timeout.

MEASURED FAILURES: (1) three Codex-backed subagents returned "started in the background as
task-…" receipts and their real work was discarded unread, because a backgrounded job's result
is unreachable to the barrier that was waiting on it; (2) a dispatch relying on a silent
10-minute default timeout is what a caller rationalised `--background` to escape.
"""

from __future__ import annotations

import pytest

from agentspec.dispatchpolicy import DISPATCH_VIOLATIONS, check_dispatch


def test_the_violation_set_is_declared_sorted_and_closed() -> None:
    assert DISPATCH_VIOLATIONS == (
        "background-on-awaited-dispatch",
        "missing-timeout",
        "nonpositive-timeout",
    )


def test_a_foreground_dispatch_with_an_explicit_timeout_is_clean() -> None:
    assert check_dispatch(background=False, timeout_s=1800, awaited=True) == ()


def test_a_backgrounded_awaited_dispatch_is_refused() -> None:
    assert check_dispatch(background=True, timeout_s=1800, awaited=True) == (
        "background-on-awaited-dispatch",
    )


def test_a_backgrounded_UNawaited_dispatch_is_allowed() -> None:
    """Detector control: the rule is scoped to dispatches a barrier is waiting on."""
    assert check_dispatch(background=True, timeout_s=1800, awaited=False) == ()


def test_a_missing_timeout_is_refused() -> None:
    assert check_dispatch(background=False, timeout_s=None, awaited=True) == ("missing-timeout",)


@pytest.mark.parametrize("bad", [0, -1])
def test_a_non_positive_timeout_is_refused(bad: int) -> None:
    assert check_dispatch(background=False, timeout_s=bad, awaited=True) == (
        "nonpositive-timeout",
    )


def test_both_violations_are_reported_together_sorted() -> None:
    assert check_dispatch(background=True, timeout_s=None, awaited=True) == (
        "background-on-awaited-dispatch",
        "missing-timeout",
    )


def test_a_float_timeout_is_refused_by_type() -> None:
    with pytest.raises(TypeError, match="int"):
        check_dispatch(background=False, timeout_s=1.5, awaited=True)  # type: ignore[arg-type]


def test_a_boolean_timeout_is_refused_by_type() -> None:
    with pytest.raises(TypeError, match="int"):
        check_dispatch(background=False, timeout_s=True, awaited=True)  # type: ignore[arg-type]
