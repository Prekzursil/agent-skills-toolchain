"""Control: xfail whose underlying bug is already fixed.

Marked execution must be XPASS; unmarked execution must PASS.
The catalog phrase is satisfied by executing both states rather than
reasoning about the reason string.
"""
import pytest


@pytest.mark.xfail(
    reason=(
        "temporary: 1+1 used to equal 3 (ISSUE-AUD-0055-STALE); "
        "remove when arithmetic works"
    )
)
def test_aud0055_stale_xfail_arithmetic_fixed():
    assert 1 + 1 == 2
