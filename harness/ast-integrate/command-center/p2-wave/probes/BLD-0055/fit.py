"""Log-log power-law fit: t ~ scale * n ** exponent.

The reviewer entry point takes only raw (n, seconds) pairs. It does not
accept an author exponent, so a re-fit cannot be steered by the claim.
"""
from __future__ import annotations

import math
from typing import Sequence


def _ols_loglog(ns: Sequence[int], ys: Sequence[float]) -> dict:
    pairs = [(int(n), float(y)) for n, y in zip(ns, ys) if n > 0 and y > 0]
    if len(pairs) < 2:
        return {
            "ok": False,
            "reason": "need-two-positive-points",
            "exponent": None,
            "scale": None,
            "residual_rms_seconds": None,
            "relative_rms": None,
            "n_points": len(pairs),
        }
    xs = [math.log(n) for n, _ in pairs]
    zs = [math.log(y) for _, y in pairs]
    k = len(xs)
    mx = sum(xs) / k
    mz = sum(zs) / k
    den = sum((x - mx) ** 2 for x in xs)
    if den == 0:
        return {
            "ok": False,
            "reason": "zero-variance-n",
            "exponent": None,
            "scale": None,
            "residual_rms_seconds": None,
            "relative_rms": None,
            "n_points": k,
        }
    num = sum((x - mx) * (z - mz) for x, z in zip(xs, zs))
    exponent = num / den
    scale = math.exp(mz - exponent * mx)
    pred = [scale * (n ** exponent) for n, _ in pairs]
    resid = math.sqrt(
        sum((p - y) ** 2 for p, (_, y) in zip(pred, pairs)) / k
    )
    rel = math.sqrt(
        sum(((p - y) / y) ** 2 for p, (_, y) in zip(pred, pairs)) / k
    )
    return {
        "ok": True,
        "reason": None,
        "exponent": exponent,
        "scale": scale,
        "residual_rms_seconds": resid,
        "relative_rms": rel,
        "n_points": k,
        "predicted_seconds": [
            {"n": n, "measured_s": y, "fitted_s": scale * (n ** exponent)}
            for n, y in pairs
        ],
    }


def classify_exponent(exponent: float | None) -> str:
    if exponent is None:
        return "UNKNOWN"
    if exponent < 0.55:
        return "sub-linear"
    if exponent <= 1.25:
        return "linear"
    if exponent < 1.70:
        return "super-linear"
    return "quadratic-or-worse"


def fit_author(ns: Sequence[int], ys: Sequence[float]) -> dict:
    """Author fit. Same estimator as the reviewer; separate entry so callsites differ."""
    out = _ols_loglog(ns, ys)
    out["fit_role"] = "author"
    out["complexity_class"] = classify_exponent(out.get("exponent"))
    return out


def fit_reviewer(raw_points: Sequence[dict]) -> dict:
    """Independent re-fit. Input is raw rows with n and wall_s only.

    Must not be passed an author exponent. Probe2 calls this before it
    reads any author_fit field off the receipt.
    """
    ns: list[int] = []
    ys: list[float] = []
    for row in raw_points:
        if not isinstance(row, dict):
            continue
        try:
            ns.append(int(row["n"]))
            ys.append(float(row["wall_s"]))
        except (KeyError, TypeError, ValueError):
            continue
    out = _ols_loglog(ns, ys)
    out["fit_role"] = "reviewer"
    out["complexity_class"] = classify_exponent(out.get("exponent"))
    out["saw_author_exponent"] = False
    return out
