"""Planted collectible node whose setup always errors.

Probe 1 (collect string-match) must see this node. Probe 2 (single-node
execution) must not count it as executable.
"""

import pytest


@pytest.fixture(autouse=True)
def _aud0038_setup_boom():
    raise RuntimeError(
        "AUD-0038 planted setup error: collectible but not executable"
    )


def test_aud0038_collectible_setup_error():
    assert True
