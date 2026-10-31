"""Control: an xfail whose bug is still LIVE - unmarking FAILS.

Still-justified case: the reason holds today.
"""
import pytest


def _still_broken_divide(value):
    return value // 0


@pytest.mark.xfail(reason="upstream bug 456 division by zero not yet fixed")
def test_aud0055_live_xfail_still_fails():
    assert _still_broken_divide(10) == 10
