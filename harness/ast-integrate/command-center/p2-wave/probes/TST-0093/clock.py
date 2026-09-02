"""Virtual clock so Retry-After waits are measured without wall-clock sleep."""
from __future__ import annotations


class VirtualClock:
    def __init__(self, start: float = 0.0) -> None:
        self.now = float(start)

    def sleep(self, seconds: float) -> None:
        if seconds < 0:
            raise ValueError("sleep cannot be negative")
        self.now += float(seconds)
