"""Yield-collapse detector for evidence saturation (TST-0283, spec :10941).

The stopping expression ``evidence_saturation == true OR time_minutes >= 180``
turns on a producer that must be shown to fire when saturation is real and to
stay silent when the evidence stream is still yielding.

Definition used here
--------------------
*Effort* is one unit of search: one retrieved evidence item.  Items are
independent when they come from distinct ``source_id`` values; padding (more
text, paraphrases, duplicate findings from a source already seen) never counts
as new independent evidence.  Effort is cut into tumbling windows of
``DetectorConfig.window`` units; the *marginal yield* of a window is
``new_independent_sources / window``.  Saturation fires at the end of the
first window that completes ``DetectorConfig.persist_windows`` consecutive
windows whose yield is below ``DetectorConfig.yield_floor``.

Ground truth comes from seeded corpora with a known number of distinct sources
(coupon-collector sampling with replacement), so every fire point can be
reported against the true source count, and a sequential stream that yields a
fresh source on every effort gives the silent-state control.

``evaluate_stopping`` keeps the two arms of the OR separate: a timeout is
logged as ``time_budget`` and can never relabel a silent detector as
``evidence_saturation``.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

# --------------------------------------------------------------------------- #
# Constants                                                                    #
# --------------------------------------------------------------------------- #

WINDOW = 8
YIELD_FLOOR = 0.125
PERSIST_WINDOWS = 4
TIME_MINUTES_FLOOR = 180
STOP_EXPRESSION = "evidence_saturation == true OR time_minutes >= 180"
INDEPENDENCE_KEY = "source_id"

BOOT_N = 1000
BOOT_SEED = 28312
BOOT_ALPHA = 0.05

N_TRIALS = 40
CANONICAL_SEED = 28312
TRIAL_SEED_BASE = 400_000
TRIAL_SEED_STRIDE = 10_000
TRIAL_SOURCE_COUNTS = (6, 12, 24)

MAX_WINDOWS = 50
STREAM_WINDOWS = 50
PADDED_TEXTS = 50
NAIVE_EFFORT_THRESHOLD = 16
PREMATURE_COVERAGE = 0.75
MIN_MEAN_COVERAGE = 0.90
LARGE_EFFECT_D = 0.8

REASON_SATURATION = "evidence_saturation"
REASON_TIME_BUDGET = "time_budget"
REASON_BOTH = "both"


# --------------------------------------------------------------------------- #
# Detector                                                                     #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class DetectorConfig:
    """Tumbling-window yield detector parameters."""

    window: int = WINDOW
    yield_floor: float = YIELD_FLOOR
    persist_windows: int = PERSIST_WINDOWS

    def __post_init__(self) -> None:
        if int(self.window) < 1:
            raise ValueError("DetectorConfig.window must be >= 1")
        if not (0.0 < float(self.yield_floor) <= 1.0):
            raise ValueError("DetectorConfig.yield_floor must be in (0, 1]")
        if int(self.persist_windows) < 1:
            raise ValueError("DetectorConfig.persist_windows must be >= 1")

    @property
    def collapse_effort(self) -> int:
        """Effort units of below-floor yield needed before the detector fires."""
        return int(self.window) * int(self.persist_windows)


DETECTOR_CONFIG = DetectorConfig()


def independence_key(item: Mapping[str, Any]) -> str:
    """Return the independence key of an evidence item (its ``source_id``)."""
    if not isinstance(item, Mapping) or INDEPENDENCE_KEY not in item:
        raise ValueError(
            f"evidence item must be a mapping with a {INDEPENDENCE_KEY!r} key; got {item!r}"
        )
    key = item[INDEPENDENCE_KEY]
    if key is None or str(key).strip() == "":
        raise ValueError(f"evidence item has an empty {INDEPENDENCE_KEY!r}: {item!r}")
    return str(key)


class SaturationDetector:
    """Stateful yield-collapse detector fed one evidence item per effort unit."""

    def __init__(self, config: DetectorConfig = DETECTOR_CONFIG) -> None:
        self.config = config
        self.effort = 0
        self.seen: set[str] = set()
        self.window_new = 0
        self.below_streak = 0
        self.windows: list[dict[str, Any]] = []
        self.fired = False
        self.fire_effort: int | None = None
        self.fire_window: int | None = None
        self.fire_yield: float | None = None
        self.last_new_effort = 0

    @property
    def discovered(self) -> int:
        return len(self.seen)

    def observe(self, item: Mapping[str, Any]) -> dict[str, Any] | None:
        """Consume one unit of effort; return the window row if a window closed."""
        key = independence_key(item)
        self.effort += 1
        if key not in self.seen:
            self.seen.add(key)
            self.window_new += 1
            self.last_new_effort = self.effort
        if self.effort % int(self.config.window) == 0:
            return self._close_window()
        return None

    def _close_window(self) -> dict[str, Any]:
        window = int(self.config.window)
        marginal_yield = self.window_new / float(window)
        below = marginal_yield < float(self.config.yield_floor)
        self.below_streak = self.below_streak + 1 if below else 0
        fired_now = False
        if not self.fired and self.below_streak >= int(self.config.persist_windows):
            self.fired = True
            fired_now = True
            self.fire_effort = self.effort
            self.fire_window = len(self.windows) + 1
            self.fire_yield = marginal_yield
        row = {
            "window_index": len(self.windows) + 1,
            "effort_end": self.effort,
            "n_new_independent": self.window_new,
            "cumulative_discovered": len(self.seen),
            "yield": marginal_yield,
            "below_floor": below,
            "fired_at_end": fired_now,
        }
        self.windows.append(row)
        self.window_new = 0
        return row


def run_detector(
    items: Iterable[Mapping[str, Any]],
    *,
    corpus_id: str,
    seed: int | None,
    true_source_count: int | None,
    config: DetectorConfig = DETECTOR_CONFIG,
    stop_at_fire: bool = True,
) -> dict[str, Any]:
    """Run the detector over ``items`` and report the fire point vs ground truth."""
    det = SaturationDetector(config)
    for item in items:
        det.observe(item)
        if stop_at_fire and det.fired:
            break
    effort_total = det.effort
    end_effort = det.fire_effort if det.fired else effort_total
    discovered = det.discovered
    if true_source_count:
        coverage = discovered / float(true_source_count)
        undiscovered = int(true_source_count) - discovered
    else:
        coverage = None
        undiscovered = None
    collapsed_before_fire = False
    if det.fired and det.fire_window is not None:
        persist = int(config.persist_windows)
        tail = det.windows[det.fire_window - persist : det.fire_window]
        collapsed_before_fire = len(tail) == persist and all(w["below_floor"] for w in tail)
    premature = bool(det.fired and coverage is not None and coverage < PREMATURE_COVERAGE)
    return {
        "corpus_id": corpus_id,
        "seed": seed,
        "true_source_count": true_source_count,
        "config": {
            "window": int(config.window),
            "yield_floor": float(config.yield_floor),
            "persist_windows": int(config.persist_windows),
        },
        "effort_total": effort_total,
        "fired": det.fired,
        "fire_effort": det.fire_effort,
        "fire_window": det.fire_window,
        "fire_yield": det.fire_yield,
        "last_new_effort": det.last_new_effort,
        "lag_after_last_new": (end_effort or 0) - det.last_new_effort,
        "discovered_at_fire_or_end": discovered,
        "undiscovered_at_fire_or_end": undiscovered,
        "coverage_at_fire_or_end": coverage,
        "collapsed_before_fire": collapsed_before_fire,
        "premature": premature,
        "windows": det.windows,
    }


def slim_windows(windows: Sequence[Mapping[str, Any]], keep: int = 8) -> list[dict[str, Any]]:
    """Return the last ``keep`` window rows (receipt-sized view of a yield curve)."""
    return [dict(w) for w in list(windows)[-int(keep) :]]


# --------------------------------------------------------------------------- #
# Seeded corpora with known ground truth                                       #
# --------------------------------------------------------------------------- #


def finite_corpus(
    n_true: int, seed: int, effort_budget: int | None = None
) -> list[dict[str, Any]]:
    """Coupon-collector corpus: ``effort_budget`` draws with replacement from ``n_true`` sources."""
    if int(n_true) < 1:
        raise ValueError("n_true must be >= 1")
    budget = int(effort_budget) if effort_budget is not None else MAX_WINDOWS * WINDOW
    rng = random.Random(seed)
    items: list[dict[str, Any]] = []
    for t in range(budget):
        k = rng.randrange(int(n_true))
        items.append(
            {
                "source_id": f"src-{k:03d}",
                "text": f"finding {t} retrieved from source {k}",
                "effort": t + 1,
            }
        )
    return items


def stream_corpus(seed: int, n_items: int | None = None) -> list[dict[str, Any]]:
    """Still-yielding control: every effort unit surfaces a never-seen source."""
    n = int(n_items) if n_items is not None else STREAM_WINDOWS * WINDOW
    return [
        {
            "source_id": f"stream-{int(seed)}-{t:04d}",
            "text": f"fresh finding {t} from a new source",
            "effort": t + 1,
        }
        for t in range(n)
    ]


def padded_corpus(seed: int, n_texts: int = PADDED_TEXTS) -> list[dict[str, Any]]:
    """Padding control: many unique texts that all come from ONE source."""
    rng = random.Random(seed)
    texts = [f"paraphrase {t} of the single source's finding" for t in range(int(n_texts))]
    rng.shuffle(texts)
    return [
        {"source_id": "src-000", "text": text, "effort": t + 1} for t, text in enumerate(texts)
    ]


def naive_effort_counter(
    items: Iterable[Mapping[str, Any]], threshold: int = NAIVE_EFFORT_THRESHOLD
) -> dict[str, Any]:
    """Token/effort counter that 'fires' after ``threshold`` items regardless of yield."""
    effort = 0
    for _ in items:
        effort += 1
        if effort >= int(threshold):
            return {"fired": True, "fire_effort": effort, "threshold": int(threshold)}
    return {"fired": False, "fire_effort": None, "threshold": int(threshold)}


# --------------------------------------------------------------------------- #
# Experiments                                                                  #
# --------------------------------------------------------------------------- #


def _curve(n_true: int, seed: int, config: DetectorConfig = DETECTOR_CONFIG) -> dict[str, Any]:
    return run_detector(
        finite_corpus(n_true, seed),
        corpus_id=f"n{int(n_true)}",
        seed=seed,
        true_source_count=int(n_true),
        config=config,
    )


def _curve_ok(curve: Mapping[str, Any]) -> bool:
    if not curve["fired"] or curve["premature"] or not curve["collapsed_before_fire"]:
        return False
    if (curve["last_new_effort"] or 0) > (curve["fire_effort"] or 0):
        return False
    coverage = curve["coverage_at_fire_or_end"]
    return coverage is not None and coverage >= PREMATURE_COVERAGE


def experiment_three_corpora(seed: int = CANONICAL_SEED) -> dict[str, Any]:
    """Yield curves for three true source counts (6, 12, 24) on one seed."""
    curves = {f"n{n}": _curve(n, seed) for n in TRIAL_SOURCE_COUNTS}
    efforts = [curves[f"n{n}"]["fire_effort"] for n in TRIAL_SOURCE_COUNTS]
    monotonic = all(e is not None for e in efforts) and all(
        efforts[i] <= efforts[i + 1] for i in range(len(efforts) - 1)
    )
    return {
        "seed": seed,
        "passed": all(_curve_ok(c) for c in curves.values()),
        "monotonic_fire_effort": monotonic,
        "curves": curves,
    }


def experiment_both_states(seed: int = CANONICAL_SEED) -> dict[str, Any]:
    """Planted-bad (finite, saturating) vs known-good (still yielding) plus controls."""
    planted = _curve(12, seed)
    planted["id"] = "finite-n12-saturated"
    planted["verbatim"] = (
        "FINITE n=12 seed={seed}: detector {state} at effort {fe} coverage={cov:.4f} "
        "vs true 12; last_new={ln} lag={lag}".format(
            seed=seed,
            state="FIRED" if planted["fired"] else "SILENT",
            fe=planted["fire_effort"],
            cov=planted["coverage_at_fire_or_end"] or 0.0,
            ln=planted["last_new_effort"],
            lag=planted["lag_after_last_new"],
        )
    )

    stream_items = stream_corpus(seed)
    stream = run_detector(
        stream_items,
        corpus_id="stream-still-yielding",
        seed=seed,
        true_source_count=len(stream_items),
    )
    stream["id"] = "stream-still-yielding"
    stream["still_yielding"] = all(
        w["yield"] >= float(DETECTOR_CONFIG.yield_floor) for w in stream["windows"]
    )
    stream["verbatim"] = (
        "STREAM still-yielding seed={seed}: detector {state} after {nw} windows; "
        "discovered={d}".format(
            seed=seed,
            state="SILENT" if not stream["fired"] else "FIRED",
            nw=len(stream["windows"]),
            d=stream["discovered_at_fire_or_end"],
        )
    )

    padded_items = padded_corpus(seed)
    padded = run_detector(
        padded_items, corpus_id="padded-unique-texts-one-source", seed=seed, true_source_count=1
    )
    padded["id"] = "padded-unique-texts-one-source"
    padded["discovered"] = padded["discovered_at_fire_or_end"]
    padded["unique_texts"] = len({item["text"] for item in padded_items})
    padded["verbatim"] = (
        f"PADDED {padded['unique_texts']} unique texts / 1 source: "
        f"discovered={padded['discovered']} fired={padded['fired']}"
    )

    naive_stream = naive_effort_counter(stream_items)
    naive_finite = naive_effort_counter(finite_corpus(12, seed))
    naive = {
        "threshold": NAIVE_EFFORT_THRESHOLD,
        "fires_on_still_yielding": naive_stream["fired"],
        "fires_on_saturated": naive_finite["fired"],
        "silent_in_neither_state": naive_stream["fired"] and naive_finite["fired"],
        "verbatim": (
            f"NAIVE effort>={NAIVE_EFFORT_THRESHOLD} counter fires on the still-yielding "
            "stream and on the saturated corpus (token counter, not yield)."
        ),
    }

    discriminates = bool(planted["fired"] and not stream["fired"])
    padding_not_inflated = bool(padded["discovered"] == 1 and padded["fired"])
    return {
        "seed": seed,
        "passed": discriminates and padding_not_inflated and naive["silent_in_neither_state"],
        "discriminates": discriminates,
        "padding_not_inflated": padding_not_inflated,
        "planted_bad": planted,
        "known_good": stream,
        "padded": padded,
        "naive_counter": naive,
    }


# --- statistics (kept formula-identical to the independent reviewer) -------- #


def _mean(xs: Sequence[float]) -> float:
    return sum(xs) / float(len(xs))


def _sd(xs: Sequence[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    m = _mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / float(n - 1))


def bootstrap_ci(
    values: Sequence[float],
    *,
    n_boot: int = BOOT_N,
    alpha: float = BOOT_ALPHA,
    seed: int = BOOT_SEED,
) -> tuple[float, float, float]:
    """Percentile bootstrap CI on the mean: (mean, lo, hi)."""
    if not values:
        raise ValueError("bootstrap_ci needs at least one value")
    rng = random.Random(seed)
    n = len(values)
    means: list[float] = []
    for _ in range(int(n_boot)):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / float(n))
    means.sort()
    lo_i = int(alpha / 2.0 * n_boot)
    hi_i = min(int(n_boot) - 1, int((1.0 - alpha / 2.0) * n_boot))
    return _mean(list(values)), means[lo_i], means[hi_i]


def cohens_d(a: Sequence[float], b: Sequence[float]) -> float:
    """Cohen's d with the pooled sample standard deviation."""
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return 0.0
    pooled = math.sqrt(((na - 1) * _sd(a) ** 2 + (nb - 1) * _sd(b) ** 2) / float(na + nb - 2))
    if pooled == 0.0:
        return 0.0
    return (_mean(a) - _mean(b)) / pooled


def trial_seed(n_true: int, trial: int, base: int = TRIAL_SEED_BASE) -> int:
    return int(base) + TRIAL_SEED_STRIDE * int(n_true) + int(trial)


def _trial_row(n_true: int, trial: int, base: int) -> dict[str, Any]:
    seed = trial_seed(n_true, trial, base)
    curve = _curve(n_true, seed)
    return {
        "n": int(n_true),
        "trial": int(trial),
        "seed": seed,
        "fired": curve["fired"],
        "fire_effort": curve["fire_effort"],
        "discovered": curve["discovered_at_fire_or_end"],
        "coverage": curve["coverage_at_fire_or_end"],
        "last_new_effort": curve["last_new_effort"],
        "premature": curve["premature"],
        "collapsed_before_fire": curve["collapsed_before_fire"],
    }


def summarize_rows(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    efforts = [
        float(r["fire_effort"]) for r in rows if r.get("fired") and r.get("fire_effort") is not None
    ]
    coverages = [float(r["coverage"]) for r in rows if r.get("fired")]
    n_fired = sum(1 for r in rows if r.get("fired"))
    if efforts:
        mean_e, lo_e, hi_e = bootstrap_ci(efforts)
    else:
        mean_e, lo_e, hi_e = (None, None, None)
    if coverages:
        mean_c, lo_c, hi_c = bootstrap_ci(coverages)
    else:
        mean_c, lo_c, hi_c = (None, None, None)
    return {
        "n_rows": len(rows),
        "n_fired": n_fired,
        "n_premature": sum(1 for r in rows if r.get("premature")),
        "fire_rate": (n_fired / float(len(rows))) if rows else 0.0,
        "mean_fire_effort": mean_e,
        "fire_effort_ci95": [lo_e, hi_e],
        "mean_coverage": mean_c,
        "coverage_ci95": [lo_c, hi_c],
        "_efforts": efforts,
    }


def experiment_trials(n_trials: int = N_TRIALS, seed_base: int = TRIAL_SEED_BASE) -> dict[str, Any]:
    """``n_trials`` seeded runs per true source count; summary with bootstrap CIs and Cohen's d."""
    if int(n_trials) < 2:
        raise ValueError("n_trials must be >= 2 for a pooled effect size")
    rows: dict[str, list[dict[str, Any]]] = {}
    per_n: dict[str, dict[str, Any]] = {}
    efforts: dict[str, list[float]] = {}
    for n in TRIAL_SOURCE_COUNTS:
        key = f"n{n}"
        rows[key] = [_trial_row(n, t, seed_base) for t in range(int(n_trials))]
        summary = summarize_rows(rows[key])
        efforts[key] = summary.pop("_efforts")
        per_n[key] = summary

    d_24_6 = cohens_d(efforts["n24"], efforts["n6"])
    d_12_6 = cohens_d(efforts["n12"], efforts["n6"])
    means = [per_n[f"n{n}"]["mean_fire_effort"] for n in TRIAL_SOURCE_COUNTS]
    monotonic = all(m is not None for m in means) and all(
        means[i] < means[i + 1] for i in range(len(means) - 1)
    )
    all_fired = all(p["n_fired"] == p["n_rows"] for p in per_n.values())
    none_premature = all(p["n_premature"] == 0 for p in per_n.values())
    coverage_ok = all(
        p["mean_coverage"] is not None and p["mean_coverage"] >= MIN_MEAN_COVERAGE
        for p in per_n.values()
    )
    passed = all_fired and none_premature and coverage_ok and monotonic and d_24_6 >= LARGE_EFFECT_D
    return {
        "n_trials": int(n_trials),
        "seed_base": int(seed_base),
        "source_counts": list(TRIAL_SOURCE_COUNTS),
        "passed": passed,
        "rows": rows,
        "summary": {
            "per_n": per_n,
            "effect_size": {
                "metric": "cohens_d_mean_fire_effort",
                "a": "n24",
                "b": "n6",
                "d": d_24_6,
                "d_n12_vs_n6": d_12_6,
                "interpretation": (
                    "Larger true source count must delay fire_effort. Cohen's d for n24 vs n6 "
                    f"mean fire_effort; {LARGE_EFFECT_D} is the large-effect floor."
                ),
            },
            "monotonic_fire_effort": monotonic,
            "pass_rule": (
                f"All trials fire; none premature (coverage<{PREMATURE_COVERAGE}); mean coverage "
                f">={MIN_MEAN_COVERAGE}; mean fire_effort increases 6<12<24; Cohen's d (n24-n6) "
                f">= {LARGE_EFFECT_D}. Bootstrap 95% CIs are on the trial means."
            ),
            "passed": passed,
        },
    }


# --------------------------------------------------------------------------- #
# Stopping expression: the OR keeps both arms distinct                         #
# --------------------------------------------------------------------------- #


def evaluate_stopping(
    evidence_saturation: bool,
    time_minutes: float,
    *,
    time_floor: float = TIME_MINUTES_FLOOR,
) -> dict[str, Any]:
    """Evaluate ``evidence_saturation == true OR time_minutes >= time_floor`` arm by arm."""
    sat_arm = bool(evidence_saturation)
    time_arm = float(time_minutes) >= float(time_floor)
    arms: list[str] = []
    if sat_arm:
        arms.append(REASON_SATURATION)
    if time_arm:
        arms.append(REASON_TIME_BUDGET)
    if sat_arm and time_arm:
        reason: str | None = REASON_BOTH
    elif sat_arm:
        reason = REASON_SATURATION
    elif time_arm:
        reason = REASON_TIME_BUDGET
    else:
        reason = None
    claims_saturation = reason in (REASON_SATURATION, REASON_BOTH)
    return {
        "expression": STOP_EXPRESSION,
        "stop": sat_arm or time_arm,
        "stop_reason": reason,
        "arms_logged": arms,
        "saturation_arm": sat_arm,
        "time_arm": time_arm,
        "detector_silent_at_timeout": time_arm and not sat_arm,
        "timeout_masked_as_saturation": claims_saturation and not sat_arm,
        "time_minutes": time_minutes,
        "evidence_saturation": sat_arm,
        "time_minutes_floor": time_floor,
    }


def experiment_time_arm(seed: int = CANONICAL_SEED) -> dict[str, Any]:
    """Show the time arm cannot mask a silent detector; both arms are logged separately."""
    under = 40
    at_floor = TIME_MINUTES_FLOOR

    finite = _curve(12, seed)
    stream = run_detector(
        stream_corpus(seed), corpus_id="stream-still-yielding", seed=seed, true_source_count=None
    )
    # A finite corpus cut off after two windows: the detector has not had
    # persist_windows of collapse yet, so it is silent although the corpus is finite.
    truncated = run_detector(
        finite_corpus(12, seed, effort_budget=2 * WINDOW),
        corpus_id="finite-n12-truncated",
        seed=seed,
        true_source_count=12,
    )

    cases = {
        "sat_only": evaluate_stopping(True, under),
        "time_only": evaluate_stopping(False, at_floor),
        "neither": evaluate_stopping(False, under),
        "both": evaluate_stopping(True, at_floor),
        "forced": evaluate_stopping(False, at_floor),
        "live_sat": evaluate_stopping(finite["fired"], under),
        "live_timeout": evaluate_stopping(stream["fired"], at_floor),
        "live_under": evaluate_stopping(stream["fired"], under),
        "live_silent_plus_timeout": evaluate_stopping(truncated["fired"], at_floor),
    }
    cases["live_sat"]["detector"] = {"corpus_id": finite["corpus_id"], "fired": finite["fired"]}
    cases["live_timeout"]["detector"] = {"corpus_id": stream["corpus_id"], "fired": stream["fired"]}
    cases["live_under"]["detector"] = {"corpus_id": stream["corpus_id"], "fired": stream["fired"]}
    cases["live_silent_plus_timeout"]["detector"] = {
        "corpus_id": truncated["corpus_id"],
        "fired": truncated["fired"],
        "windows_seen": len(truncated["windows"]),
    }

    def _is(case: str, *, stop: bool, reason: str | None, silent: bool | None = None) -> bool:
        c = cases[case]
        ok = c["stop"] is stop and c["stop_reason"] == reason and not c["timeout_masked_as_saturation"]
        if silent is not None:
            ok = ok and c["detector_silent_at_timeout"] is silent
        return ok

    checks = {
        "sat_only_ok": _is("sat_only", stop=True, reason=REASON_SATURATION, silent=False)
        and cases["sat_only"]["arms_logged"] == [REASON_SATURATION],
        "time_only_ok": _is("time_only", stop=True, reason=REASON_TIME_BUDGET, silent=True)
        and cases["time_only"]["arms_logged"] == [REASON_TIME_BUDGET],
        "neither_ok": _is("neither", stop=False, reason=None, silent=False)
        and cases["neither"]["arms_logged"] == [],
        "both_ok": _is("both", stop=True, reason=REASON_BOTH, silent=False)
        and cases["both"]["arms_logged"] == [REASON_SATURATION, REASON_TIME_BUDGET],
        "forced_ok": _is("forced", stop=True, reason=REASON_TIME_BUDGET, silent=True),
        "live_sat_ok": finite["fired"] and _is("live_sat", stop=True, reason=REASON_SATURATION),
        "live_timeout_ok": (not stream["fired"])
        and _is("live_timeout", stop=True, reason=REASON_TIME_BUDGET, silent=True),
        "live_under_ok": (not stream["fired"]) and _is("live_under", stop=False, reason=None),
    }
    live_silent_ok = (not truncated["fired"]) and _is(
        "live_silent_plus_timeout", stop=True, reason=REASON_TIME_BUDGET, silent=True
    )
    return {
        "seed": seed,
        "expression": STOP_EXPRESSION,
        "time_minutes_floor": TIME_MINUTES_FLOOR,
        "passed": all(checks.values()) and live_silent_ok and not stream["fired"],
        "checks": checks,
        "live_silent_plus_timeout_ok": live_silent_ok,
        "stream_fired": stream["fired"],
        "finite_fired": finite["fired"],
        "cases": cases,
    }


__all__ = [
    "BOOT_ALPHA",
    "BOOT_N",
    "BOOT_SEED",
    "CANONICAL_SEED",
    "DETECTOR_CONFIG",
    "DetectorConfig",
    "INDEPENDENCE_KEY",
    "N_TRIALS",
    "PERSIST_WINDOWS",
    "REASON_BOTH",
    "REASON_SATURATION",
    "REASON_TIME_BUDGET",
    "STOP_EXPRESSION",
    "SaturationDetector",
    "TIME_MINUTES_FLOOR",
    "TRIAL_SEED_BASE",
    "WINDOW",
    "YIELD_FLOOR",
    "bootstrap_ci",
    "cohens_d",
    "evaluate_stopping",
    "experiment_both_states",
    "experiment_three_corpora",
    "experiment_time_arm",
    "experiment_trials",
    "finite_corpus",
    "independence_key",
    "naive_effort_counter",
    "padded_corpus",
    "run_detector",
    "slim_windows",
    "stream_corpus",
    "summarize_rows",
    "trial_seed",
]
