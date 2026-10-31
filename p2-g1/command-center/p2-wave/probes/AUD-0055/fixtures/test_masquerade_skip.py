"""Control: a skip whose stated reason claims temporary, but the body passes today.

Masquerade case: permanent disablement dressed as a temporary pause.
"""
import pytest


@pytest.mark.skip(reason="temporarily disabled pending rewrite")
def test_aud0055_masquerade_skip_would_pass():
    assert sorted([3, 1, 2]) == [1, 2, 3]
