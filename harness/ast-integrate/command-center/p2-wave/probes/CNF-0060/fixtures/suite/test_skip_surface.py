"""Skip / xfail / deselect surface for CNF-0060.

test_planted_target currently FAILS. The detector control plants an
unconditional skip on it — disabling instead of fixing. Passed count stays
put; executed count drops.
"""
from __future__ import annotations

import sys

from pytest_shim import pytest


def test_stable_pass() -> None:
    assert 1 + 1 == 2


def test_another_pass() -> None:
    assert "ok"


@pytest.mark.skip(reason="ticket-123: parked flake, not a fix")
def test_unconditional_skip() -> None:
    assert False, "must not run"


@pytest.mark.skipif(
    sys.platform.startswith("win"),
    reason="windows-only named pipe",
)
def test_windows_named_pipe() -> None:
    assert True


@pytest.mark.skipif(
    not sys.platform.startswith("win"),
    reason="posix-only fork semantics",
)
def test_posix_fork() -> None:
    assert True


@pytest.mark.xfail(reason="bug-456: trailing comma still rejected")
def test_xfail_trailing_comma() -> None:
    raise AssertionError("still broken")


def test_deselected_slow() -> None:
    assert True


def test_planted_target() -> None:
    assert False, "bug still present — skip would hide this"


def test_runtime_skip() -> None:
    pytest.skip("runtime: extra dataset missing")
