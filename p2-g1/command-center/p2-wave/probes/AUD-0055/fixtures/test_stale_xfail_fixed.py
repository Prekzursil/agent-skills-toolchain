"""Control: an xfail whose underlying bug is FIXED - unmarking PASSES.

Stale case: the reason no longer holds.
"""
import pytest


def _now_fixed_parse(value):
    return int(value)


@pytest.mark.xfail(reason="upstream bug 123 divides by zero on empty input")
def test_aud0055_stale_xfail_fixed():
    assert _now_fixed_parse("42") == 42
