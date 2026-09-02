"""Control: xfail whose underlying bug is still present.

Marked execution must be XFAIL; unmarked execution must FAIL.
This is the both-states pair for the stale-xfail control.
"""
import pytest


@pytest.mark.xfail(
    reason="still broken: zero-division (ISSUE-AUD-0055-LIVE); not a stale skip"
)
def test_aud0055_still_broken_zero_div():
    assert 1 / 0 == 1
