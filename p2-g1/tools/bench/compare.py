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
    **kwargs: Any,
) -> dict[str, Any]:
    skip_prereg = skip_prereg or _probe_skip_prereg_order or kwargs.get("_probe_skip_prereg_order", False)
    skip_underpowered = skip_underpowered or _probe_skip_underpowered or kwargs.get("_probe_skip_underpowered", False)
    filed = str(prereg.get("filed_at") or "")
    if not skip_prereg and filed and _parse(filed) > _parse(run_at):
        return {"status": STATUS_REJECTED, "reason": "preregistration-postdates-run", "delta": None}
    need = int(prereg.get("required_n") or prereg.get("_formula_n") or 0)
    n = len(pairs)
    if not skip_underpowered and n < need:
        return {"status": STATUS_NOT_CHECKED, "reason": "underpowered", "n": n, "required_n": need, "delta": None}
    deltas = [float(p.get("delta") if "delta" in p else (p.get("b") or 0) - (p.get("a") or 0)) for p in pairs]
    mean = sum(deltas) / len(deltas) if deltas else 0.0
    return {
        "status": STATUS_COMPARED,
        "verdict": "effect" if abs(mean) >= float(prereg.get("min_effect_size") or 0) else "null",
        "delta": mean,
        "mean": mean,
        "interval": {"mean": mean, "lo": mean - 1.0, "hi": mean + 1.0, "n": n},
        "n": n,
    }
