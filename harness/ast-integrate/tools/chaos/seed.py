"""Deterministic seed derivation."""
from __future__ import annotations


def derive_params(seed: int) -> dict[str, int]:
    s = int(seed)
    return {
        "delay_ms": 10 + (s % 50),
        "jump_s": 1 + (s % 7),
        "jump_forward_s": 3 + (s % 11),
        "freeze_probe_s": 1,
    }
