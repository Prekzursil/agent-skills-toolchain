"""Control: skipif(True) - an unconditional skip in conditional clothing.
"""
import pytest

UNCONDITIONAL = True


@pytest.mark.skipif(UNCONDITIONAL, reason="windows-only development harness")
def test_aud0055_skipif_true_unconditional():
    assert True
