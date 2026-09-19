"""Token/compute cost estimation for ``biomni_cost``.

These are *estimates* for a rolling meter and per-run breakdown. The
authoritative token balance always comes from the online backend's
``bm_billing_balance`` (surfaced by ``biomni_cost`` when available); compute
cost for self-host backends comes from the databricks adapter's DBU meter.
Prices are USD per 1M tokens and are easy to update as vendor pricing moves.
"""

from __future__ import annotations

# USD per 1M tokens (input, output). Keyed by a normalized model id.
PRICING: dict[str, tuple[float, float]] = {
    "claude-sonnet": (3.0, 15.0),
    "claude-opus": (15.0, 75.0),
    "claude-haiku": (0.80, 4.0),
    "gpt-4o": (2.50, 10.0),
    "default": (3.0, 15.0),  # assume Sonnet-class (Biomni parity default)
}

# Rough all-purpose single-node DBU price for the databricks warm cluster.
DBU_USD_PER_HOUR = 0.55


def normalize_model(model: str | None) -> str:
    if not model:
        return "default"
    m = model.lower()
    for key in PRICING:
        if key != "default" and key in m:
            return key
    if "sonnet" in m:
        return "claude-sonnet"
    if "opus" in m:
        return "claude-opus"
    if "haiku" in m:
        return "claude-haiku"
    return "default"


def estimate_token_cost(
    tokens_in: int, tokens_out: int, model: str | None = None
) -> float:
    """Estimate USD for a token spend given a model id."""
    rate_in, rate_out = PRICING[normalize_model(model)]
    return round(
        (max(0, tokens_in) / 1_000_000) * rate_in
        + (max(0, tokens_out) / 1_000_000) * rate_out,
        6,
    )


def estimate_compute_cost(
    duration_s: float, dbu_per_hour: float = DBU_USD_PER_HOUR
) -> float:
    """Estimate self-host compute USD from wall-clock seconds."""
    return round((max(0.0, duration_s) / 3600.0) * dbu_per_hour, 6)
