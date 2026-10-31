"""Experiment design: required n vs budget."""
from __future__ import annotations


def design(effect_size: float, budget_n_per_arm: int | None = None) -> dict:
    # Two-sample n per arm for d=0.5 ~ 64.
    required = int(round(16.0 / max(abs(effect_size), 0.05) ** 2))
    required = max(16, min(200, required))
    if budget_n_per_arm is not None and budget_n_per_arm < required:
        return {"verdict": "STOP", "required_n_per_arm": required, "budget_n_per_arm": budget_n_per_arm}
    return {"verdict": "PROCEED", "required_n_per_arm": required}
