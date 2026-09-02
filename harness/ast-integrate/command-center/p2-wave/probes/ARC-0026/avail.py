"""Observable availability signal for deferred (lazy) activation.

A collapsed 'unavailable' bit cannot separate not-selected from not-installed.
The required observable is three independent bits plus activation status,
emitted at the moment the capability is not usable.
"""
from __future__ import annotations

from typing import Any

CODES = (
    "AVAILABLE",
    "NOT_SELECTED",
    "NOT_INSTALLED",
    "INDEX_MISS_INSTALLED",
    "STALE_INDEX",
    "ACTIVATION_FAILED",
    "ACTIVATION_PENDING",
    "DEACTIVATED_RESIDUAL",
)

ACTIVATIONS = ("never", "pending", "ok", "failed", "deactivated")


def classify(
    *,
    indexed: bool,
    installed: bool,
    selected: bool,
    activation: str = "never",
    residual_state: bool = False,
) -> dict[str, Any]:
    if activation not in ACTIVATIONS:
        raise ValueError(f"bad activation {activation!r}")
    code: str
    if activation == "deactivated" and residual_state:
        code = "DEACTIVATED_RESIDUAL"
    elif selected and activation == "failed":
        code = "ACTIVATION_FAILED"
    elif selected and activation == "pending":
        code = "ACTIVATION_PENDING"
    elif selected and activation == "ok" and indexed and installed:
        code = "AVAILABLE"
    elif indexed and not installed:
        code = "STALE_INDEX"
    elif (not indexed) and installed:
        code = "INDEX_MISS_INSTALLED"
    elif (not indexed) and (not installed):
        code = "NOT_INSTALLED"
    elif indexed and installed and not selected:
        code = "NOT_SELECTED"
    elif selected and indexed and installed:
        code = "AVAILABLE"
    else:
        code = "NOT_INSTALLED"
    return {
        "indexed": bool(indexed),
        "installed": bool(installed),
        "selected": bool(selected),
        "activation": activation,
        "residual_state": bool(residual_state),
        "code": code,
        "observable": (
            f"indexed={int(indexed)} installed={int(installed)} "
            f"selected={int(selected)} activation={activation} "
            f"residual={int(residual_state)} -> {code}"
        ),
    }


def collapsed_unavailable(*, selected: bool) -> str:
    """Broken single-bit signal: ignores index and install."""
    return "AVAILABLE" if selected else "UNAVAILABLE"
