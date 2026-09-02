"""Scientific replication protocol gate.

A replication is judged on two things: the *protocol* (was the effect size
declared up front, is the protocol identified, were the required steps run) and
the *result* (a two-sample summary whose observed effect must reproduce the
declared one and be significant at the declared alpha). Either failing yields
``REJECTED``; both passing yields ``REPLICATED``.
"""
from __future__ import annotations

import math

REQUIRED_STEPS = frozenset({"declare-d", "collect", "report-effect-size"})
REPLICATED = "REPLICATED"
REJECTED = "REJECTED"
# Observed |d| may fall short of the declared effect by at most this fraction.
EFFECT_TOLERANCE = 0.5


def _two_sided_p(z: float) -> float:
    return math.erfc(abs(z) / math.sqrt(2.0))


def observed_effect(result: dict) -> dict:
    """Cohen's d, standard error and two-sided p for a two-sample summary."""
    n_a, n_b = int(result["n_a"]), int(result["n_b"])
    sd_a, sd_b = float(result["sd_a"]), float(result["sd_b"])
    diff = float(result["mean_b"]) - float(result["mean_a"])
    if n_a < 2 or n_b < 2:
        raise ValueError("each arm needs n >= 2")
    pooled_var = ((n_a - 1) * sd_a**2 + (n_b - 1) * sd_b**2) / (n_a + n_b - 2)
    pooled_sd = math.sqrt(pooled_var)
    if pooled_sd <= 0:
        raise ValueError("pooled sd must be positive")
    d = diff / pooled_sd
    se = pooled_sd * math.sqrt(1.0 / n_a + 1.0 / n_b)
    z = diff / se
    return {"d": d, "se": se, "z": z, "p_two_sided": _two_sided_p(z)}


def protocol_check(protocol: dict) -> dict:
    steps = set(protocol.get("steps") or [])
    missing = sorted(REQUIRED_STEPS - steps)
    reasons = []
    if not protocol.get("protocol_id"):
        reasons.append("no-protocol-id")
    if not protocol.get("effect_size"):
        reasons.append("no-declared-effect-size")
    if missing:
        reasons.append("missing-steps")
    return {
        "ok": not reasons,
        "protocol_id": protocol.get("protocol_id") or None,
        "missing": missing,
        "reasons": reasons,
    }


def replicate(protocol: dict, result: dict | None = None) -> dict:
    """Judge a replication attempt.

    ``protocol`` declares ``protocol_id``, ``effect_size`` and ``steps``;
    ``result`` is a two-sample summary (``mean_a``, ``mean_b``, ``sd_a``,
    ``sd_b``, ``n_a``, ``n_b``, optional ``alpha``). Returns the protocol check
    plus ``verdict`` (``REPLICATED``/``REJECTED``) and the reasons.
    """
    report = protocol_check(protocol)
    reasons = list(report["reasons"])
    stats: dict | None = None
    if result is None:
        reasons.append("no-result")
    else:
        alpha = float(result.get("alpha", 0.05))
        try:
            stats = observed_effect(result)
        except (KeyError, TypeError, ValueError) as exc:
            reasons.append(f"unusable-result:{exc}")
        else:
            declared = float(protocol.get("effect_size") or 0.0)
            if stats["p_two_sided"] >= alpha:
                reasons.append("not-significant")
            if declared:
                if math.copysign(1.0, stats["d"]) != math.copysign(1.0, declared):
                    reasons.append("effect-direction-reversed")
                elif abs(stats["d"]) < abs(declared) * (1.0 - EFFECT_TOLERANCE):
                    reasons.append("effect-smaller-than-declared")
    verdict = REPLICATED if not reasons else REJECTED
    return {
        **report,
        "ok": not reasons,
        "verdict": verdict,
        "reasons": reasons,
        "result_id": None if result is None else result.get("id"),
        "observed": stats,
    }
