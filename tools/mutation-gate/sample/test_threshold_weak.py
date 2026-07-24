"""WEAK test -- gate goes RED.

It gives ``threshold.py`` 100% LINE coverage, yet it never exercises the ``==``
boundary nor the ``DEFAULT_MIN_BYTES`` default (it always passes ``min_bytes``
explicitly). So the mutants ``>=`` -> ``>`` and ``DEFAULT_MIN_BYTES`` -> 1025/1023
SURVIVE: the tests run the line but do not assert its behaviour.
"""

from threshold import is_large_enough


def test_is_large_enough_explicit():
    assert is_large_enough(2048, min_bytes=512) is True
    assert is_large_enough(100, min_bytes=512) is False
