"""The injected CLOCK port. There is no real clock in this package.

Determinism is a regression row: two runs of the same spec must produce identical artifacts,
so nothing on the dispatch path may read a wall clock or draw entropy.
:func:`agentspec.determinism.scan_package` enforces that mechanically over this package's own
source — which is why this module deliberately ships NO ``SystemClock``. A live transport
supplies one; the pure core never does.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Clock(Protocol):
    """Milliseconds since an arbitrary, caller-defined epoch. Monotonic."""

    def now_ms(self) -> int: ...


class FixedClock:
    """A deterministic clock: time moves ONLY when :meth:`advance` is called."""

    __slots__ = ("_now_ms",)

    def __init__(self, start_ms: int = 0) -> None:
        if start_ms < 0:
            raise ValueError("start_ms must be >= 0")
        self._now_ms = start_ms

    def now_ms(self) -> int:
        return self._now_ms

    def advance(self, ms: int) -> int:
        """Move time forward by ``ms`` and return the new reading."""
        if isinstance(ms, bool) or not isinstance(ms, int):
            raise TypeError(f"ms must be an int, not {type(ms).__name__}")
        if ms < 0:
            raise ValueError("a clock is monotonic: ms must be >= 0")
        self._now_ms += ms
        return self._now_ms


def elapsed_ms(start_ms: int, end_ms: int) -> int:
    """Pure interval over two readings of the SAME clock."""
    if end_ms < start_ms:
        raise ValueError("a clock is monotonic: end_ms must be >= start_ms")
    return end_ms - start_ms
