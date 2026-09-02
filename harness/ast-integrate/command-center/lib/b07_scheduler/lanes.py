"""Lane math: batch_ceiling consults interactive_reserved."""
from __future__ import annotations


def batch_ceiling(capacity: int, interactive_reserved: int, reservation_enabled: bool) -> int:
    if reservation_enabled:
        return max(0, int(capacity) - int(interactive_reserved))
    return int(capacity)
