"""Forge engine (IMP-0254)."""
from __future__ import annotations

from typing import Any

from tools.foundry import counters


class ForgeError(RuntimeError):
    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code


def run_forge(payload: dict[str, Any]) -> dict[str, Any]:
    counters.inc("forge.run")
    counters.inc("forge.simulate")
    if payload.get("broken_input"):
        raise ForgeError("typed-failure", "broken input")
    return {
        "workflow": {
            "certified": True,
            "operator": "adopt",
            "id": "forged-incumbent-rtv",
        }
    }
