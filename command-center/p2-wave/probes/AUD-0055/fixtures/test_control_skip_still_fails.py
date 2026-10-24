"""AUD-0055 control: skip whose reason still holds.

Removing the skip must FAIL the test. That proves Probe 2 executes the
unmarked sample rather than inventing a reason-validity verdict.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(
    reason="AUD-0055-CONTROL: deliberately broken assertion; skip still required"
)
def test_aud0055_control_skip_still_fails():
    assert False, "reason still holds: unmarked run must FAIL"
