"""The injected CLOCK port. There is no real clock in this package.

Determinism is a regression row: two runs of the same spec must produce identical artifacts,
so nothing on the dispatch path may read a wall clock or draw entropy.
:func:`agentspec.determinism.scan_package` enforces that mechanically over this package's own
source — which is why this module deliberately ships NO ``SystemClock``. A live transport
supplies one; the pure core never does.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Clock(Protocol):
    """Milliseconds since an arbitrary, caller-defined epoch. Monotonic."""

    def now_ms(self) -> int: ...


@runtime_checkable
class SteppableClock(Clock, Protocol):
    """A clock a harness can step explicitly — the port the fake rail needs.

    Kept separate from :class:`Clock` so a production consumer can inject a read-only clock
    while the eval rail demands one it can drive. That also removes a duck-typing branch from
    the rail: no ``getattr(clock, "advance", None)`` fallback, so no untestable arm.
    """

    def advance(self, ms: int) -> int: ...


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


class FakeClock(FixedClock):
    """Harness alias used by IMP-0221 probes. Same contract as FixedClock."""


def elapsed_ms(start_ms: int, end_ms: int) -> int:
    """Pure interval over two readings of the SAME clock."""
    if end_ms < start_ms:
        raise ValueError("a clock is monotonic: end_ms must be >= start_ms")
    return end_ms - start_ms


# --- TST-0029 DAG replay ports (ns + pid). Additive; FixedClock is unchanged. ---
import os
import time as _time


class FrozenClock:
    def __init__(self, clock_ns: int = 0) -> None:
        self._ns = int(clock_ns)

    def now_ns(self) -> int:
        return self._ns

    def now_ms(self) -> int:
        return self._ns // 1_000_000


class WallClock:
    def now_ns(self) -> int:
        return _time.time_ns()

    def now_ms(self) -> int:
        return int(_time.time() * 1000)


class FixedPid:
    def __init__(self, value: int) -> None:
        self._value = int(value)

    def pid(self) -> int:
        return self._value


class LivePid:
    def pid(self) -> int:
        return os.getpid()


class Host:
    def __init__(
        self,
        clock: Any,
        pid: Any,
        seed: int,
        leak_clock_into_fanout: bool = False,
        leak_pid_into_ready: bool = False,
    ) -> None:
        self.clock = clock
        self._pid = pid
        self.seed = int(seed)
        self.leak_clock_into_fanout = bool(leak_clock_into_fanout)
        self.leak_pid_into_ready = bool(leak_pid_into_ready)

    def now_ns(self) -> int:
        return int(self.clock.now_ns())

    def now_ms(self) -> int:
        if hasattr(self.clock, "now_ms"):
            return int(self.clock.now_ms())
        return self.now_ns() // 1_000_000

    def pid(self) -> int:
        src = self._pid
        if hasattr(src, "pid"):
            return int(src.pid())
        return int(src)


def frozen_host(
    seed: int,
    clock_ns: int = 0,
    pid: int = 4242,
    leak_clock_into_fanout: bool = False,
    leak_pid_into_ready: bool = False,
) -> Host:
    return Host(
        FrozenClock(clock_ns),
        FixedPid(pid),
        seed,
        leak_clock_into_fanout=leak_clock_into_fanout,
        leak_pid_into_ready=leak_pid_into_ready,
    )


def wall_host(
    seed: int,
    pid: Any = None,
    leak_clock_into_fanout: bool = False,
    leak_pid_into_ready: bool = False,
) -> Host:
    return Host(
        WallClock(),
        LivePid() if pid is None else pid,
        seed,
        leak_clock_into_fanout=leak_clock_into_fanout,
        leak_pid_into_ready=leak_pid_into_ready,
    )


class FakeClock:
    """Deterministic injected clock in seconds (IMP-0220 stagger rail)."""

    __slots__ = ("_now", "sleep_calls")

    def __init__(self, start: float | int = 0.0) -> None:
        self._now = float(start)
        self.sleep_calls: list[float] = []

    def now(self) -> float:
        return self._now

    def now_ms(self) -> int:
        return int(self._now * 1000)

    def sleep(self, seconds: float) -> None:
        seconds = float(seconds)
        if seconds < 0:
            raise ValueError("sleep must be >= 0")
        self.sleep_calls.append(seconds)
        self._now += seconds

    def advance(self, ms: int) -> int:
        if isinstance(ms, bool) or not isinstance(ms, int):
            raise TypeError(f"ms must be an int, not {type(ms).__name__}")
        if ms < 0:
            raise ValueError("a clock is monotonic: ms must be >= 0")
        self._now += ms / 1000.0
        return self.now_ms()
