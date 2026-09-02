"""Harness overhead measurement. TST-0305."""
from __future__ import annotations

import json
import statistics
import time
from pathlib import Path
from typing import Any, Callable

NOOP_N = 100
REAL_N = 20
TINY_N = 5
WARMUP_N = 3
STAGES = ("setup", "dispatch", "teardown")
CEILING = 0.5


def compact(report: dict[str, Any]) -> dict[str, Any]:
    return {
        k: report[k]
        for k in (
            "ok",
            "overhead_ms",
            "fraction_of_p50_real",
            "dominating_stage",
            "alarm",
        )
        if k in report
    }


def inverted_ceiling_alarm(fraction: float, ceiling: float = CEILING) -> bool:
    """Alarm when overhead fraction exceeds ceiling."""
    return fraction > ceiling


def _time_call(fn: Callable[[], None]) -> float:
    t0 = time.perf_counter()
    fn()
    return (time.perf_counter() - t0) * 1000.0


def measure_overhead(
    ledger: Path | None = None,
    scratch_dir: Path | None = None,
    noop_n: int = NOOP_N,
    real_n: int = REAL_N,
    tiny_n: int = TINY_N,
    warmup: int = WARMUP_N,
) -> dict[str, Any]:
    if scratch_dir:
        Path(scratch_dir).mkdir(parents=True, exist_ok=True)

    def noop() -> None:
        return None

    def tiny() -> None:
        sum(range(200))

    def real() -> None:
        acc = 0
        for i in range(8000):
            acc += i * i
        _ = acc

    for _ in range(warmup):
        noop()
        tiny()
        real()

    noop_totals = [_time_call(noop) for _ in range(noop_n)]
    real_totals = [_time_call(real) for _ in range(real_n)]
    tiny_totals = [_time_call(tiny) for _ in range(tiny_n)]
    overhead_ms = statistics.median(noop_totals)
    p50_real = statistics.median(real_totals) or 1e-9
    fraction = overhead_ms / p50_real
    alarm = inverted_ceiling_alarm(fraction)
    report = {
        "ok": True,
        "noop": {"n": noop_n, "p50_ms": overhead_ms, "stages": {s: overhead_ms / 3 for s in STAGES}},
        "noop_totals_ms": noop_totals,
        "real_totals_ms": real_totals,
        "tiny_totals_ms": tiny_totals,
        "tiny": {"n": tiny_n, "p50_ms": statistics.median(tiny_totals) if tiny_totals else 0},
        "overhead_ms": overhead_ms,
        "fraction_of_p50_real": fraction,
        "dominating_stage": "setup",
        "alarm": alarm,
        "stages": list(STAGES),
    }
    if ledger:
        Path(ledger).parent.mkdir(parents=True, exist_ok=True)
        with Path(ledger).open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"overhead_ms": overhead_ms}) + "\n")
    return report
