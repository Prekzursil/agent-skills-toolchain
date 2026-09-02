"""Negative controls: tests that CAN produce a red must not enter the census."""

from __future__ import annotations

import sys

import pytest


def test_negative_has_assertion_tst0126() -> None:
    assert 1 + 1 == 2


@pytest.mark.skipif(False, reason="TST-0126 skipif(False) must not count as skip")
def test_negative_skipif_false_tst0126() -> None:
    assert True


@pytest.mark.skipif(
    sys.platform == "tst0126-nonexistent-os",
    reason="TST-0126 runtime skipif must not count as unconditional",
)
def test_negative_skipif_expr_tst0126() -> None:
    assert True


@pytest.mark.xfail(False, reason="TST-0126 xfail(False) must not count as always-xfail")
def test_negative_xfail_false_tst0126() -> None:
    assert True


@pytest.mark.xfail(
    condition=sys.version_info < (0,),
    reason="TST-0126 conditional xfail must not count as always-xfail",
)
def test_negative_xfail_expr_tst0126() -> None:
    assert True


def test_negative_raises_can_fail_tst0126() -> None:
    with pytest.raises(ValueError):
        raise ValueError("tst-0126")
