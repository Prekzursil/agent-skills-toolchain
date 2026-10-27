"""HUD spawn-budget measurement (TST-0238)."""
from __future__ import annotations

from .statusline import SPAWN_CEILING
from .spawn_measure import install_shims, prove_shim_catches_known_spawn, run_statusline

__all__ = [
    "SPAWN_CEILING",
    "install_shims",
    "prove_shim_catches_known_spawn",
    "run_statusline",
]
