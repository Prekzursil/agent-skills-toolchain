"""Injected CLOCK and PID ports for TST-0029 DAG replay.

Production scheduling must not read these. Leak flags on Host are the detector
control: they are the sites a defective scheduler would use (DynamicFanOut
cardinality from now_ns; ready-set order from pid).

Wall-clock surface (scanned): Date.now() analogue via time.time_ns.
PID surface (scanned): os.getpid.
"""

from __future__ import annotations

import os
import time
from typing import Any


class FrozenClock:
    """Pinned nanoseconds. Two runs with the same origin match."""

    def __init__(self, clock_ns: int = 0) -> None:
        self._ns = int(clock_ns)

    def now_ns(self) -> int:
        return self._ns


class WallClock:
    """Live wall clock. Date.now() analogue — must not enter production traces."""

    def now_ns(self) -> int:
        return time.time_ns()


class FixedPid:
    def __init__(self, value: int) -> None:
        self._value = int(value)

    def pid(self) -> int:
        return self._value


class LivePid:
    def pid(self) -> int:
        return os.getpid()


class Host:
    """Clock + pid + seed + optional leak flags for detector controls."""

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
