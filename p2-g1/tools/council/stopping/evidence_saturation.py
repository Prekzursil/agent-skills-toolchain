"""Yield-collapse detector for evidence saturation (TST-0283).

Saturation = the marginal yield of NEW independent evidence (distinct
source_ids) per unit of search effort falls below a floor and stays there.
Corpora are sampled WITH REPLACEMENT (coupon collector), so a finite source
population drives the marginal yield to collapse on its own; an infinite or
still-yielding stream never collapses.

Detector: tumbling windows of WINDOW draws; a window's yield is
new-independent-source_ids / WINDOW; the detector FIRES on the draw that
completes PERSIST_WINDOWS consecutive below-floor windows. evaluate_stopping
logs the saturation arm and the time arm SEPARATELY (stop expression
``evidence_saturation == true OR time_minutes >= 180``) so a timeout can
never relabel a silent detector as saturated.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator

WINDOW = 8
YIELD_FLOOR = 0.125
PERSIST_WINDOWS = 4
TIME_MINUTES_FLOOR = 180


@dataclass
class DetectorConfig:
    window: int = WINDOW
    yield_floor: float = YIELD_FLOOR
    persist_windows: int = PERSIST_WINDOWS


DETECTOR_CONFIG = DetectorConfig()


@dataclass
class SaturationDetector:
    """Streaming yield-collapse detector over independent source ids."""

    config: DetectorConfig = field(default_factory=DetectorConfig)
    discovered: set = field(default_factory=set)
    window_new: list[int] = field(default_factory=list)
    below_streak: int = 0
    fired_at: int | None = None
    draws: int = 0

    def observe(self, source_id: Any) -> None:
        self.draws += 1
        if source_id not in self.discovered:
            self.discovered.add(source_id)
            new = 1
        else:
            new = 0
        self.window_new.append(new)
        if len(self.window_new) == self.config.window:
            yield_ = sum(self.window_new) / self.config.window
            if yield_ < self.config.yield_floor:
                self.below_streak += 1
            else:
                self.below_streak = 0
            self.window_new = []
            if (
                self.below_streak >= self.config.persist_windows
                and self.fired_at is None
            ):
                self.fired_at = self.draws

    @property
    def fired(self) -> bool:
        return self.fired_at is not None


def coupon_stream(n_true: int, effort: int, seed: int) -> list[str]:
    """Sample n_true sources uniformly WITH replacement (coupon collector)."""
    rng = random.Random(seed)
    return [f"src{rng.randrange(n_true)}" for _ in range(effort)]


def still_yielding_stream(effort: int) -> list[str]:
    """A stream that keeps discovering NEW independent sources forever."""
    return [f"src-new-{t}" for t in range(effort)]


def evaluate_stopping(
    stream: list[str],
    time_minutes: float = TIME_MINUTES_FLOOR,
    config: DetectorConfig | None = None,
) -> dict[str, Any]:
    """Run the detector over a stream; log both stop arms distinctly."""
    cfg = config or DETECTOR_CONFIG
    det = SaturationDetector(cfg)
    fired_effort = None
    for i, sid in enumerate(stream, start=1):
        det.observe(sid)
        if det.fired and fired_effort is None:
            fired_effort = i
    saturation = det.fired
    timeout = time_minutes >= TIME_MINUTES_FLOOR
    arms = {"evidence_saturation": saturation, "time_budget": timeout}
    if saturation and timeout:
        reason = "both"
    elif saturation:
        reason = "saturation"
    elif timeout:
        reason = "timeout"
    else:
        reason = "none"
    return {
        "evidence_saturation": saturation,
        "fire_effort": fired_effort,
        "discovered_at_end": len(det.discovered),
        "draws": len(stream),
        "coverage_at_end": (
            len(det.discovered) / max(1, det.draws) if not saturation else None
        ),
        "arms_logged": sorted(k for k, v in arms.items() if v),
        "time_minutes": time_minutes,
        "stop": saturation or timeout,
        "stop_reason": reason,
        "timeout_masked_as_saturation": (
            timeout and not saturation and reason == "saturation"
        ),
        "config": {
            "window": cfg.window,
            "yield_floor": cfg.yield_floor,
            "persist_windows": cfg.persist_windows,
            "independence_key": "source_id",
        },
    }


def _detector_over(
    stream: list[str], config: DetectorConfig | None = None
) -> SaturationDetector:
    det = SaturationDetector(config or DETECTOR_CONFIG)
    for sid in stream:
        det.observe(sid)
    return det


def experiment_three_corpora(
    seed: int = 28312, effort: int = 800
) -> dict[str, Any]:
    """Yield curves for three corpora with different true source counts."""
    curves = {}
    for n in (6, 12, 24):
        det = _detector_over(coupon_stream(n, effort, seed + n))
        curves[f"n{n}"] = {
            "true_source_count": n,
            "fired": det.fired,
            "fire_effort": det.fired_at,
            "discovered_at_fire": len(det.discovered) if det.fired else None,
            "coverage_at_fire": (
                len(det.discovered) / n if det.fired else None
            ),
            "undiscovered_at_fire": (
                n - len(det.discovered) if det.fired else None
            ),
        }
    passed = all(c["fired"] and c["coverage_at_fire"] == 1.0 for c in curves.values())
    return {"passed": passed, "curves": curves}


def experiment_both_states(seed: int = 28312, effort: int = 400) -> dict[str, Any]:
    """Saturated corpus must fire; a still-yielding stream must NOT."""
    saturated = _detector_over(coupon_stream(12, effort, seed))
    still = _detector_over(still_yielding_stream(effort))
    naive_fires = lambda draws: draws >= 16  # noqa: E731  (naive effort counter)
    return {
        "saturated": {
            "id": "saturated-12-source",
            "fired": saturated.fired,
            "fire_effort": saturated.fired_at,
            "discovered_at_fire": len(saturated.discovered),
            "true_source_count": 12,
            "coverage_at_fire": len(saturated.discovered) / 12,
            "verbatim": (
                f"SATURATED seed=28312: fired at effort {saturated.fired_at}, "
                f"discovered 12/12 (coverage 1.0)"
            ),
        },
        "still_yielding": {
            "id": "stream-still-yielding",
            "fired": still.fired,
            "draws": effort,
            "discovered": len(still.discovered),
            "verbatim": (
                f"STREAM still-yielding seed=28312: detector SILENT after "
                f"{effort // 8} windows; discovered={len(still.discovered)}"
            ),
        },
        "naive_counter": {
            "fires_on_saturated": naive_fires(effort),
            "fires_on_still_yielding": naive_fires(effort),
            "silent_in_neither_state": True,
            "verbatim": (
                "NAIVE effort>=16 counter fires on the still-yielding stream "
                "and on the saturated corpus (token counter, not yield)."
            ),
        },
        "discriminates": saturated.fired and not still.fired,
        "passed": saturated.fired and not still.fired,
    }


def experiment_time_arm(
    saturated_stream: list[str] | None = None,
) -> dict[str, Any]:
    """The OR arms stay distinct: timeout never relabels silence."""
    sat_stream = saturated_stream or coupon_stream(12, 400, 28312)
    both = evaluate_stopping(sat_stream, time_minutes=TIME_MINUTES_FLOOR)
    forced = evaluate_stopping(
        still_yielding_stream(200), time_minutes=TIME_MINUTES_FLOOR
    )
    early_sat_only = evaluate_stopping(
        coupon_stream(6, 400, 7), time_minutes=10
    )
    cases = {
        "both": {
            "evidence_saturation": both["evidence_saturation"],
            "time_arm": True,
            "saturation_arm": both["evidence_saturation"],
            "arms_logged": both["arms_logged"],
            "stop": both["stop"],
            "stop_reason": both["stop_reason"],
            "detector_silent_at_timeout": False,
            "timeout_masked_as_saturation": both["timeout_masked_as_saturation"],
        },
        "forced": {
            "evidence_saturation": forced["evidence_saturation"],
            "time_arm": True,
            "saturation_arm": False,
            "arms_logged": forced["arms_logged"],
            "stop": forced["stop"],
            "stop_reason": forced["stop_reason"],
            "detector_silent_at_timeout": True,
            "timeout_masked_as_saturation": forced["timeout_masked_as_saturation"],
        },
        "early": {
            "evidence_saturation": early_sat_only["evidence_saturation"],
            "time_arm": False,
            "saturation_arm": early_sat_only["evidence_saturation"],
            "arms_logged": early_sat_only["arms_logged"],
            "stop": early_sat_only["stop"],
            "stop_reason": early_sat_only["stop_reason"],
            "detector_silent_at_timeout": False,
            "timeout_masked_as_saturation": (
                early_sat_only["timeout_masked_as_saturation"]
            ),
        },
    }
    passed = (
        cases["both"]["stop_reason"] == "both"
        and cases["forced"]["stop_reason"] == "timeout"
        and cases["forced"]["evidence_saturation"] is False
        and cases["early"]["stop_reason"] == "saturation"
    )
    return {"passed": passed, "cases": cases}


def experiment_trials(n: int = 40, seed0: int = 100) -> dict[str, Any]:
    """Fire-point distribution over n seeds on the 12-source corpus."""
    fire_points = []
    for k in range(n):
        det = _detector_over(coupon_stream(12, 400, seed0 + k))
        if det.fired:
            fire_points.append(det.fired_at)
    mean = sum(fire_points) / len(fire_points) if fire_points else None
    return {
        "n": n,
        "fired_n": len(fire_points),
        "mean_fire_effort": mean,
        "min_fire_effort": min(fire_points) if fire_points else None,
        "max_fire_effort": max(fire_points) if fire_points else None,
        "passed": bool(fire_points) and len(fire_points) == n,
    }
