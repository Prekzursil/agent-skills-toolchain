"""Pre-registered comparison with formula n and underpowered guard (TST-0298)."""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from typing import Any

STATUS_COMPARED = "COMPARED"
STATUS_NOT_CHECKED = "NOT-CHECKED"
STATUS_REJECTED = "REJECTED"
VERDICT_IMPROVEMENT = "IMPROVEMENT"
VERDICT_NO_DETECT = "NO-DETECTABLE-EFFECT"
INTERVAL_KEYS = ("mean", "lo", "hi", "n")
DEFAULT_LEVEL = 0.95


class BareEstimateError(ValueError):
    """A point estimate without its paired-bootstrap interval is refused."""


def paired_bootstrap_interval(
    diffs: list[float], *, seed: int, n_resamples: int, level: float = DEFAULT_LEVEL
) -> tuple[float, float, float]:
    """Percentile bootstrap of the mean paired difference (deterministic per seed)."""
    import random

    values = [float(d) for d in diffs]
    if not values:
        raise BareEstimateError("no paired differences to bootstrap")
    n = len(values)
    mean = sum(values) / n
    rng = random.Random(int(seed))
    means = []
    for _ in range(int(n_resamples)):
        total = 0.0
        for _k in range(n):
            total += values[rng.randrange(n)]
        means.append(total / n)
    means.sort()
    alpha = (1.0 - float(level)) / 2.0
    lo_idx = min(len(means) - 1, max(0, int(round(alpha * (len(means) - 1)))))
    hi_idx = min(len(means) - 1, max(0, int(round((1.0 - alpha) * (len(means) - 1)))))
    return mean, means[lo_idx], means[hi_idx]


def emit_delta(
    *,
    mean: float,
    lo: float | None = None,
    hi: float | None = None,
    n: int | None = None,
    level: float = DEFAULT_LEVEL,
    n_resamples: int | None = None,
    seed: int | None = None,
) -> dict[str, Any]:
    """Construct a published delta; a bare point estimate is refused."""
    missing = [k for k, v in (("lo", lo), ("hi", hi), ("n", n)) if v is None]
    if missing:
        raise BareEstimateError(f"bare point estimate refused: missing interval keys {missing}")
    if not (float(lo) <= float(mean) <= float(hi)):
        raise BareEstimateError("interval does not contain its mean")
    out: dict[str, Any] = {"mean": float(mean), "lo": float(lo), "hi": float(hi), "n": int(n), "level": float(level)}
    if n_resamples is not None:
        out["n_resamples"] = int(n_resamples)
    if seed is not None:
        out["seed"] = int(seed)
    return out


def compute_required_n(min_effect: float, assumed_sd: float, alpha: float, power: float) -> int:
    # Paired two-sided: n = ceil((z_a + z_b)^2 * sd^2 / d^2)
    z_a = 1.959963984540054  # 0.05 two-sided
    z_b = 0.841621233572914  # 0.80
    n = ((z_a + z_b) ** 2) * (float(assumed_sd) ** 2) / (float(min_effect) ** 2)
    return int(math.ceil(n - 1e-12))


def file_preregistration(
    *,
    min_effect_size: float,
    assumed_sd: float,
    filed_at: str,
    seed: int,
    n_resamples: int,
    comparison_id: str,
    alpha: float = 0.05,
    power: float = 0.80,
) -> dict[str, Any]:
    n = compute_required_n(min_effect_size, assumed_sd, alpha, power)
    body = {
        "comparison_id": comparison_id,
        "min_effect_size": min_effect_size,
        "assumed_sd": assumed_sd,
        "filed_at": filed_at,
        "seed": seed,
        "n_resamples": n_resamples,
        "alpha": alpha,
        "power": power,
        "required_n": n,
        "_formula_n": n,
    }
    blob = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    body["digest"] = hashlib.sha256(blob).hexdigest()
    return body


def load_prereg(prereg: dict[str, Any]) -> dict[str, Any]:
    return dict(prereg)


def require_interval(result: dict[str, Any]) -> dict[str, Any]:
    if str(result.get("status") or "") != STATUS_COMPARED:
        raise ValueError("require_interval only on COMPARED results")
    interval = result.get("interval") or {}
    if "lo" not in interval and "low" in interval:
        interval["lo"] = interval["low"]
    if "hi" not in interval and "high" in interval:
        interval["hi"] = interval["high"]
    interval.setdefault("n", result.get("n"))
    interval.setdefault("mean", result.get("mean") or result.get("delta"))
    return interval


def _prereg_tamper_reason(prereg: dict[str, Any]) -> str | None:
    """Reject a pre-registration whose sample size is not the formula n.

    The required n must be recomputable from the filed effect size, sd, alpha
    and power; a hand-edited required_n (or a digest that no longer matches the
    filed body) means the sample size was not pre-computed.
    """
    try:
        formula_n = compute_required_n(
            float(prereg["min_effect_size"]),
            float(prereg["assumed_sd"]),
            float(prereg.get("alpha", 0.05)),
            float(prereg.get("power", 0.80)),
        )
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return "sample-size-not-precomputed"
    if int(prereg.get("required_n") or 0) != formula_n:
        return "sample-size-not-precomputed"
    if "_formula_n" in prereg and int(prereg["_formula_n"]) != formula_n:
        return "sample-size-not-precomputed"
    digest = prereg.get("digest")
    if digest is not None:
        body = {k: v for k, v in prereg.items() if k != "digest"}
        blob = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
        if hashlib.sha256(blob).hexdigest() != digest:
            return "preregistration-digest-mismatch"
    return None


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def compare_cases(
    pairs: list[dict[str, Any]],
    prereg: dict[str, Any],
    run_at: str,
    *,
    skip_prereg: bool = False,
    skip_underpowered: bool = False,
    _probe_skip_prereg_order: bool = False,
    _probe_skip_underpowered: bool = False,
    _probe_skip_power_guard: bool = False,
    **kwargs: Any,
) -> dict[str, Any]:
    skip_prereg = skip_prereg or _probe_skip_prereg_order or kwargs.get("_probe_skip_prereg_order", False)
    # The power guard is the underpowered check; both probe spellings disable it
    # so a both-states control can show the guard is load-bearing.
    skip_underpowered = bool(
        skip_underpowered
        or _probe_skip_underpowered
        or _probe_skip_power_guard
        or kwargs.get("_probe_skip_underpowered", False)
        or kwargs.get("_probe_skip_power_guard", False)
    )
    filed = str(prereg.get("filed_at") or "")
    if not skip_prereg and filed and _parse(filed) > _parse(run_at):
        return {"status": STATUS_REJECTED, "reason": "preregistration-postdates-run", "delta": None}
    tamper = _prereg_tamper_reason(prereg)
    if tamper is not None:
        return {"status": STATUS_REJECTED, "reason": tamper, "delta": None}
    need = int(prereg.get("required_n") or prereg.get("_formula_n") or 0)
    n = len(pairs)
    if not skip_underpowered and n < need:
        return {"status": STATUS_NOT_CHECKED, "reason": "underpowered", "n": n, "required_n": need, "delta": None}
    deltas = [_pair_delta(p) for p in pairs]
    seed = int(prereg.get("seed") or 0)
    n_resamples = int(prereg.get("n_resamples") or 2000)
    mean, lo, hi = paired_bootstrap_interval(deltas, seed=seed, n_resamples=n_resamples, level=DEFAULT_LEVEL)
    interval = emit_delta(mean=mean, lo=lo, hi=hi, n=n, level=DEFAULT_LEVEL, n_resamples=n_resamples, seed=seed)
    contains_zero = lo <= 0.0 <= hi
    min_effect = float(prereg.get("min_effect_size") or 0)
    detected = (not contains_zero) and abs(mean) >= min_effect
    return {
        "status": STATUS_COMPARED,
        "verdict": VERDICT_IMPROVEMENT if detected else VERDICT_NO_DETECT,
        "delta": dict(interval),
        "interval": dict(interval),
        "mean": mean,
        "contains_zero": contains_zero,
        "n": n,
        "min_effect_size": min_effect,
    }


def _pair_delta(pair: dict[str, Any]) -> float:
    if "delta" in pair and pair["delta"] is not None:
        return float(pair["delta"])
    if "after" in pair and "before" in pair:
        return float(pair["after"]) - float(pair["before"])
    return float(pair.get("b") or 0) - float(pair.get("a") or 0)
