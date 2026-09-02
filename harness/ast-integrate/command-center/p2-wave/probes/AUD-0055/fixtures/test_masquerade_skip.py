"""Permanently disabled test masquerading as temporary.

Reason uses temporary language and has no expiry. The body PASSES when
the skip is removed, so the skip is not protecting a failure.
"""
import pytest


@pytest.mark.skip(reason="temporarily disabled pending rewrite")
def test_aud0055_masquerade_skip_would_pass():
    assert True
