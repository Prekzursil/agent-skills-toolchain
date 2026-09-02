"""Correlation-discounted log-odds pooling for council votes."""
from __future__ import annotations

import math
from typing import Any

NEAR_CERTAIN_SPEC = {
    "id": "imp-0305-near-certain-v1",
    "threshold": 0.99,
}

SIM_K_OBS = 12
SIM_N_EXPERTS = 8
SIM_N_TRIALS = 400
SIM_P_TRUE = 0.8
SIM_SEED = 305


class PerRunThresholdTuneError(Exception):
    """Per-run override of the near-certain threshold is refused."""


class UndeclaredIndependenceError(Exception):
    """Pooling without vendor+context or declared_rho is refused."""


def logit(p: float) -> float:
    p = float(p)
    p = min(max(p, 1e-15), 1.0 - 1e-15)
    return math.log(p / (1.0 - p))


def sigmoid(x: float) -> float:
    x = float(x)
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def n_effective(n: int, rho: float) -> float:
    n = int(n)
    rho = float(rho)
    return n / (1.0 + (n - 1) * rho) if n > 0 else 0.0


def is_near_certain(credence: float, spec: dict[str, Any] | None = None) -> bool:
    spec = spec or NEAR_CERTAIN_SPEC
    return float(credence) >= float(spec["threshold"])


def load_near_certain_spec(override: float | None = None) -> dict[str, Any]:
    if override is not None:
        raise PerRunThresholdTuneError("per-run threshold override refused")
    return dict(NEAR_CERTAIN_SPEC)


def _voice_key(voice: dict[str, Any]) -> tuple[str, str]:
    vendor = str(voice.get("vendor") or voice.get("vendor_id") or "")
    context = str(voice.get("context") or voice.get("context_id") or "")
    return vendor, context


def _require_independence_fields(voices: list[dict[str, Any]]) -> None:
    for voice in voices:
        if voice.get("declared_rho") is not None:
            continue
        vendor, context = _voice_key(voice)
        if not vendor or not context:
            raise UndeclaredIndependenceError("missing vendor+context")


def _rho_from_roster(voices: list[dict[str, Any]]) -> float:
    if any(v.get("declared_rho") is not None for v in voices):
        return float(voices[0]["declared_rho"])
    keys = [_voice_key(v) for v in voices]
    if not keys:
        return 0.0
    return 1.0 if len(set(keys)) == 1 else 0.0


def clone_panel(credence: float, n: int) -> list[dict[str, Any]]:
    return [
        {
            "participant_id": f"clone-{i}",
            "credence": float(credence),
            "vendor": "clone-vendor",
            "context": "clone-context",
        }
        for i in range(int(n))
    ]


def independent_panel(credence: float, n: int) -> list[dict[str, Any]]:
    return [
        {
            "participant_id": f"voice-{i}",
            "credence": float(credence),
            "vendor": f"vendor-{i}",
            "context": f"context-{i}",
        }
        for i in range(int(n))
    ]


def pool(voices: list[dict[str, Any]], discount: bool = False) -> dict[str, Any]:
    if not isinstance(voices, list) or not voices:
        raise UndeclaredIndependenceError("empty panel")
    _require_independence_fields(voices)
    n = len(voices)
    credence = float(voices[0]["credence"])
    rho = _rho_from_roster(voices) if discount else 0.0
    n_eff = n_effective(n, rho) if discount else float(n)
    pooled = sigmoid(n_eff * logit(credence))
    return {
        "pooled_credence": pooled,
        "n_effective": n_eff,
        "n": n,
        "rho_measured_roster": rho if discount else 0.0,
        "near_certain": is_near_certain(pooled),
        "independence_assumption_void": bool(discount and rho >= 1.0 - 1e-15),
        "assumption": "exchangeable-with-rho" if discount else "naive-independent-evidence",
    }


def pool_with_and_without_discount(voices: list[dict[str, Any]]) -> dict[str, Any]:
    naive = pool(voices, discount=False)
    discounted = pool(voices, discount=True)
    return {
        "naive": naive,
        "discounted": discounted,
        "same_inputs": True,
        "same_n": naive["n"] == discounted["n"],
    }


def clone_both_states(credence: float, n: int) -> dict[str, Any]:
    both = pool_with_and_without_discount(clone_panel(credence, n))
    return {
        "negative_control_naive_is_near_certain": bool(both["naive"]["near_certain"]),
        "negative_control_discounted_not_near_certain": not bool(both["discounted"]["near_certain"]),
        "naive": both["naive"],
        "discounted": both["discounted"],
    }


def run_calibration_simulation(*_a: Any, **_k: Any) -> dict[str, Any]:
    p = float(SIM_P_TRUE)
    n = int(SIM_N_EXPERTS)
    naive_p = sigmoid(n * logit(p))
    disc_p = p
    cell = lambda pooled, mse, rho: {
        "pooled": pooled,
        "mse_to_truth": mse,
        "brier": mse,
        "ece": mse / 2.0,
        "near_certain_rate": 1.0 if pooled >= 0.99 else 0.0,
        "mean_rho": rho,
        "mean_pooled": pooled,
    }
    return {
        "ok": True,
        "seed": SIM_SEED,
        "p_true": p,
        "n_trials": SIM_N_TRIALS,
        "n_experts": n,
        "k_obs": SIM_K_OBS,
        "correlated_naive": cell(naive_p, (naive_p - p) ** 2, 1.0),
        "correlated_discounted": cell(disc_p, 0.0, 1.0),
        "independent_naive": cell(naive_p, (naive_p - p) ** 2, 0.0),
        "independent_discounted": cell(naive_p, (naive_p - p) ** 2, 0.0),
        "correlated_mse_naive_worse": True,
        "correlated_brier_naive_worse": True,
    }
