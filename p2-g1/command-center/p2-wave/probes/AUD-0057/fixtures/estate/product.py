"""Planted replica of the DEFAULT_MIN_BYTES hole for AUD-0057.

Historical measurement: reverting DEFAULT_MIN_BYTES 1024 -> 512 left a 15/15
green suite because every test passed min_bytes explicitly. Line coverage on
the body can still be 100% while the default itself is dead.

aud0057_scale_by_factor() is the both-states control: tests omit factor, so
mutating that default must turn the suite red.
"""

from __future__ import annotations

DEFAULT_MIN_BYTES = 1024


def aud0057_check_payload_floor(
    payload: bytes, min_bytes: int = DEFAULT_MIN_BYTES
) -> bool:
    """Return True when payload meets the size floor.

    The body is fully line-coverable without ever reading the default.
    """
    if not isinstance(payload, (bytes, bytearray)):
        raise TypeError("payload must be bytes")
    return len(payload) >= min_bytes


def aud0057_scale_by_factor(value: int, factor: int = 2) -> int:
    """Exercised-default control: tests call this without factor."""
    return value * factor
