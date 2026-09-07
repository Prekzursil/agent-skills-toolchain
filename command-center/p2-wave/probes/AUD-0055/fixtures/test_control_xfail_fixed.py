"""AUD-0055 control: xfail whose underlying bug is already fixed.

Marked xfail with a stale reason. The assertion is true today, so pytest
must report XPASS while marked. Probe 2 removes the marker in a scratch
worktree and must observe PASS (sample executed, not reasoned about).
"""

from __future__ import annotations

import pytest

# Stale reason on purpose: the "bug" (wrong expectation) was fixed.
@pytest.mark.xfail(
    reason="AUD-0055-CONTROL: historic off-by-one in 1+1; still broken",
    strict=False,
)
def test_aud0055_control_xfail_fixed():
    assert 1 + 1 == 2
