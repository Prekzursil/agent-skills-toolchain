"""STRONG test -- gate goes GREEN.

The strengthened version pins the default threshold with LITERAL values (not the
imported ``DEFAULT_MIN_BYTES`` symbol, which would move together with the mutation)
and checks the ``==`` boundary directly. Every mutant the weak test left alive is
now killed, so the gate reports zero survivors.
"""

from threshold import is_large_enough


def test_default_threshold_is_1024_exactly():
    assert is_large_enough(1024) is True  # exactly the default (== boundary)
    assert is_large_enough(1023) is False  # one below the default
    assert is_large_enough(1025) is True  # one above the default


def test_explicit_threshold_boundary():
    assert is_large_enough(512, min_bytes=512) is True  # == boundary
    assert is_large_enough(511, min_bytes=512) is False
    assert is_large_enough(513, min_bytes=512) is True
