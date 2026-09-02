"""skipif(True) is an unconditional skip with a fake future expiry."""
import pytest


@pytest.mark.skipif(True, reason="temporary platform guard until 2099-01-01")
def test_aud0055_skipif_always_would_pass():
    assert True
