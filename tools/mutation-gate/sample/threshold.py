"""Self-demo target for the TG-2 mutation gate.

A deliberately tiny threshold check. It is trivial to reach 100% *line* coverage
on it while leaving the boundary (``>=`` vs ``>``) and the default constant
unasserted -- exactly the ``DEFAULT_MIN_BYTES`` scar the gate exists to catch.
"""

DEFAULT_MIN_BYTES = 1024


def is_large_enough(size, min_bytes=DEFAULT_MIN_BYTES):
    """Return True when ``size`` meets the minimum byte threshold."""
    return size >= min_bytes
