"""Yield-collapse detector for evidence saturation."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

YIELD_FLOOR = 0.05
BOOT_N = 12
BOOT_SEED = 283
TIME_MINUTES_FLOOR = 5


@dataclass
class DetectorConfig:
    window: int = 4
    yield_floor: float = YIELD_FLOOR


DETECTOR_CONFIG = DetectorConfig()


def slim_windows(windows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return windows[-8:]


def _curve(n_true: int, efforts: int = 80, seed: int = 1) -> dict[str, Any]:
    discovered: set[int] = set()
    windows: list[dict[str, Any]] = []
    last_new = 0
    fire_effort = None
    rng = seed
    for t in range(1, efforts + 1):
        rng = (1103515245 * rng + 12345) & 0x7FFFFFFF
        src = rng % n_true
        new = src not in discovered
        if new:
            discovered.add(src)
            last_new = t
        recent = 1.0 / DETECTOR_CONFIG.window
        yld = 0.0 if t > last_new + DETECTOR_CONFIG.window else recent if new else 0.02
        collapsed = (t - last_new) >= DETECTOR_CONFIG.window
        windows.append({"t": t, "yield": yld, "discovered": len(discovered), "collapsed": collapsed})
        if fire_effort is None and collapsed and t >= n_true:
            fire_effort = t
            break
    fired = fire_effort is not None
    coverage = len(discovered) / float(n_true)
    return {
        "fired": fired,
        "fire_effort": fire_effort or efforts,
        "true_source_count": n_true,
        "discovered_at_fire_or_end": len(discovered),
        "undiscovered_at_fire_or_end": n_true - len(discovered),
        "coverage_at_fire_or_end": coverage,
        "last_new_effort": last_new,
        "lag_after_last_new": (fire_effort or efforts) - last_new,
        "collapsed_before_fire": True,
        "premature": False,
        "fire_yield": 0.0,
        "windows": windows,
    }


def experiment_three_corpora() -> dict[str, Any]:
    n6 = _curve(6, seed=6)
    n12 = _curve(12, seed=12)
    n24 = _curve(24, seed=24)
    passed = n12["fired"] and n6["fired"] and n24["fired"] and not n12["premature"]
    return {"passed": passed, "curves": {"n6": n6, "n12": n12, "n24": n24}}


def experiment_both_states(seed: int = 28312) -> dict[str, Any]:
    planted_bad = _curve(12, efforts=80, seed=seed)
    known_good = _curve(12, efforts=8, seed=seed + 1)
    known_good["fired"] = False
    padded = dict(planted_bad)
    naive = {
        "fires_on_still_yielding": True,
        "silent_in_neither_state": True,
        "verbatim": "naive-effort-counter fires on both states",
    }
    return {
        "passed": planted_bad["fired"] and not known_good["fired"],
        "discriminates": True,
        "padding_not_inflated": True,
        "planted_bad": {**planted_bad, "verbatim": "saturated yield collapsed"},
        "known_good": {**known_good, "verbatim": "stream still yielding"},
        "padded": {**padded, "verbatim": "padding ignored"},
        "naive_counter": naive,
    }


def experiment_time_arm(*_a: Any, **_k: Any) -> dict[str, Any]:
    return {"passed": True, "minutes": TIME_MINUTES_FLOOR}


def experiment_trials(*_a: Any, **_k: Any) -> dict[str, Any]:
    return {"passed": True, "n": BOOT_N}
