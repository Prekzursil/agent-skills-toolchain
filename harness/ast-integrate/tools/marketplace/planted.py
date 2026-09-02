"""Planted SBOM fixtures for IMP-0092."""
from __future__ import annotations

from typing import Any

from tools.marketplace.sbom_registry import SBOM_ABSENT, SbomRegistry

PLANTED_NAME = "requests"
PLANTED_VER = "2.31.0"
ZERO_NAME = "no-such-component"
ZERO_VER = "0.0.0"
ABSENT_PKG = "pkg-delta"
ABSENT_VER = "9.9.9"


def populate(reg: SbomRegistry) -> dict[str, Any]:
    alpha = reg.publish(
        "pkg-alpha",
        "1.0.0",
        {"components": [{"name": PLANTED_NAME, "version": PLANTED_VER}]},
    )
    beta = reg.publish(
        "pkg-beta",
        "2.1.0",
        {
            "components": [
                {"name": PLANTED_NAME, "version": PLANTED_VER},
                {"name": "flask", "version": "3.0.0"},
            ]
        },
    )
    gamma = reg.publish(
        "pkg-gamma",
        "0.4.0",
        {"components": [{"name": "flask", "version": "3.0.0"}]},
    )
    delta = reg.publish(ABSENT_PKG, ABSENT_VER, None)
    epsilon = reg.publish("pkg-epsilon", "0.0.1", {"components": "not-a-list"})
    return {
        "alpha": alpha,
        "beta": beta,
        "gamma": gamma,
        "delta": delta,
        "epsilon_rejected": epsilon,
    }
