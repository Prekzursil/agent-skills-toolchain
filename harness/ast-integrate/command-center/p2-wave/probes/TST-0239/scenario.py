#!/usr/bin/env python3
"""Live measurements for TST-0239: cold vs warm first-command, plus scaling."""
from __future__ import annotations

import math
import statistics
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

from first_command import (
    BASE_N,
    BODY_BYTES,
    first_command,
    seed_install,
)

TRIALS_STATES = 7
TRIALS_SCALE = 5
SCALES = (1, 4, 16)
REPRESENTATIVE_SCALE = 4
# Hard ceiling for representative-size cold start (milliseconds).
COLD_CEILING_MS = 4000.0
MIN_COLD_OVER_WARM = 2.0
MAX_LINEAR_EXPONENT = 1.45
MIN_QUADRATIC_EXPONENT = 1.65
MAX_TWO_WARM_RATIO = 1.45
MIN_CACHE_DELETE_OVER_WARM = 1.6


def _median(xs: list[float]) -> float:
    if not xs:
        raise ValueError("empty sample")
    return float(statistics.median(xs))


def _time_call(fn: Callable[[], Any]) -> tuple[float, Any]:
    t0 = time.perf_counter()
    out = fn()
    ms = (time.perf_counter() - t0) * 1000.0
    return ms, out


def _trials(fn: Callable[[], Any], n: int) -> tuple[list[float], Any]:
    samples: list[float] = []
    last = None
    for _ in range(n):
        ms, last = _time_call(fn)
        samples.append(ms)
    return samples, last


def measure_both_states(*, n: int | None = None, trials: int = TRIALS_STATES) -> dict[str, Any]:
    """Timed cold and warm first-command on a clean isolated profile."""
    size = int(n if n is not None else BASE_N * REPRESENTATIVE_SCALE)
    with tempfile.TemporaryDirectory(prefix="tst0239-states-") as tmp:
        profile = Path(tmp)
        seed_install(profile, size)

        cold_samples, cold_last = _trials(
            lambda: first_command(profile, force_cold=True, builder="linear"),
            trials,
        )
        # Cache now exists; warm runs must not rebuild.
        warm_samples, warm_last = _trials(
            lambda: first_command(profile, force_cold=False, builder="linear"),
            trials,
        )
        warm_again_samples, _ = _trials(
            lambda: first_command(profile, force_cold=False, builder="linear"),
            max(3, trials // 2),
        )
        # Detector: deleting the cache must restore cold-like cost.
        deleted_samples, deleted_last = _trials(
            lambda: first_command(profile, force_cold=True, builder="linear"),
            max(3, trials // 2),
        )

    cold_ms = _median(cold_samples)
    warm_ms = _median(warm_samples)
    warm2_ms = _median(warm_again_samples)
    deleted_ms = _median(deleted_samples)
    speedup = (cold_ms / warm_ms) if warm_ms > 0 else float("inf")
    two_warm = (max(warm_ms, warm2_ms) / min(warm_ms, warm2_ms)) if min(warm_ms, warm2_ms) > 0 else 999.0
    deleted_over_warm = (deleted_ms / warm_ms) if warm_ms > 0 else float("inf")

    modes_ok = (
        isinstance(cold_last, dict)
        and cold_last.get("mode") == "cold"
        and isinstance(warm_last, dict)
        and warm_last.get("mode") == "warm"
        and isinstance(deleted_last, dict)
        and deleted_last.get("mode") == "cold"
        and int(cold_last.get("count") or 0) == size
        and int(warm_last.get("count") or 0) == size
    )
    faster = speedup >= MIN_COLD_OVER_WARM
    under = cold_ms <= COLD_CEILING_MS
    two_warm_not_a_signal = two_warm <= MAX_TWO_WARM_RATIO
    cache_control = deleted_over_warm >= MIN_CACHE_DELETE_OVER_WARM
    passed = bool(modes_ok and faster and under and two_warm_not_a_signal and cache_control)

    return {
        "probe": "both-states",
        "n": size,
        "body_bytes": BODY_BYTES,
        "trials": trials,
        "cold_samples_ms": [round(x, 4) for x in cold_samples],
        "warm_samples_ms": [round(x, 4) for x in warm_samples],
        "warm_repeat_samples_ms": [round(x, 4) for x in warm_again_samples],
        "cache_deleted_samples_ms": [round(x, 4) for x in deleted_samples],
        "cold_median_ms": round(cold_ms, 4),
        "warm_median_ms": round(warm_ms, 4),
        "warm_repeat_median_ms": round(warm2_ms, 4),
        "cache_deleted_median_ms": round(deleted_ms, 4),
        "cold_over_warm": round(speedup, 4),
        "two_warm_ratio": round(two_warm, 4),
        "cache_deleted_over_warm": round(deleted_over_warm, 4),
        "ceiling_ms": COLD_CEILING_MS,
        "under_ceiling": under,
        "warm_measurably_faster": faster,
        "two_warms_do_not_distinguish": two_warm_not_a_signal,
        "cache_delete_restores_cold": cache_control,
        "modes_ok": modes_ok,
        "pass": passed,
    }


def _cold_median(n: int, builder: str, trials: int) -> float:
    with tempfile.TemporaryDirectory(prefix="tst0239-scale-") as tmp:
        profile = Path(tmp)
        seed_install(profile, n)
        samples, last = _trials(
            lambda: first_command(profile, force_cold=True, builder=builder),  # type: ignore[arg-type]
            trials,
        )
        if not isinstance(last, dict) or last.get("mode") != "cold":
            raise RuntimeError(f"expected cold mode for n={n} builder={builder}")
        if int(last.get("count") or 0) != n:
            raise RuntimeError(f"count {last.get('count')} != {n}")
    return _median(samples)


def _exponent(t_hi: float, t_lo: float, ratio_n: float) -> float:
    if t_lo <= 0 or t_hi <= 0 or ratio_n <= 1:
        return float("inf")
    return math.log(t_hi / t_lo) / math.log(ratio_n)


def measure_scaling(*, trials: int = TRIALS_SCALE) -> dict[str, Any]:
    """1x / 4x / 16x cold first-command, plus quadratic-mutant detector."""
    linear_ms: dict[str, float] = {}
    points: list[dict[str, Any]] = []
    for scale in SCALES:
        n = BASE_N * scale
        ms = _cold_median(n, "linear", trials)
        linear_ms[str(scale)] = ms
        points.append(
            {
                "scale": scale,
                "n": n,
                "cold_median_ms": round(ms, 4),
                "ms_per_capability": round(ms / n, 6),
            }
        )

    t1 = linear_ms["1"]
    t4 = linear_ms["4"]
    t16 = linear_ms["16"]
    exp_16 = _exponent(t16, t1, 16.0)
    exp_4 = _exponent(t4, t1, 4.0)
    ratio_16 = t16 / t1 if t1 > 0 else float("inf")
    linear_ok = exp_16 <= MAX_LINEAR_EXPONENT and ratio_16 <= 16.0 * 2.5

    q1 = _cold_median(BASE_N * 1, "quadratic", max(3, trials - 1))
    q4 = _cold_median(BASE_N * 4, "quadratic", max(3, trials - 1))
    q_exp = _exponent(q4, q1, 4.0)
    q_ratio = q4 / q1 if q1 > 0 else float("inf")
    quadratic_detected = q_exp >= MIN_QUADRATIC_EXPONENT and q_exp > exp_4 + 0.35

    representative = linear_ms[str(REPRESENTATIVE_SCALE)]
    under = representative <= COLD_CEILING_MS
    passed = bool(linear_ok and quadratic_detected and under)

    return {
        "probe": "scaling",
        "base_n": BASE_N,
        "scales": list(SCALES),
        "points": points,
        "linear_t1_ms": round(t1, 4),
        "linear_t4_ms": round(t4, 4),
        "linear_t16_ms": round(t16, 4),
        "t16_over_t1": round(ratio_16, 4),
        "exponent_1x_16x": round(exp_16, 4),
        "exponent_1x_4x": round(exp_4, 4),
        "max_linear_exponent": MAX_LINEAR_EXPONENT,
        "linear_on": linear_ok,
        "quadratic_t1_ms": round(q1, 4),
        "quadratic_t4_ms": round(q4, 4),
        "quadratic_t4_over_t1": round(q_ratio, 4),
        "quadratic_exponent_1x_4x": round(q_exp, 4),
        "min_quadratic_exponent": MIN_QUADRATIC_EXPONENT,
        "quadratic_mutant_detected": quadratic_detected,
        "representative_scale": REPRESENTATIVE_SCALE,
        "representative_cold_ms": round(representative, 4),
        "ceiling_ms": COLD_CEILING_MS,
        "under_ceiling": under,
        "characterization": (
            "O(n)"
            if linear_ok
            else ("superlinear" if exp_16 > 1.6 else "unbounded-or-noisy")
        ),
        "pass": passed,
    }


def measure_all() -> dict[str, Any]:
    both = measure_both_states()
    scaling = measure_scaling()
    passed = bool(both.get("pass") and scaling.get("pass"))
    return {
        "pass": passed,
        "both_states": both,
        "scaling": scaling,
        "answer": {
            "cold_median_ms": both["cold_median_ms"],
            "warm_median_ms": both["warm_median_ms"],
            "cold_over_warm": both["cold_over_warm"],
            "representative_n": both["n"],
            "ceiling_ms": COLD_CEILING_MS,
            "under_ceiling": both["under_ceiling"] and scaling["under_ceiling"],
            "scaling_exponent_1x_16x": scaling["exponent_1x_16x"],
            "index_build_is_unbounded": not scaling["linear_on"],
            "characterization": scaling["characterization"],
            "quadratic_detector_fired": scaling["quadratic_mutant_detected"],
        },
    }
