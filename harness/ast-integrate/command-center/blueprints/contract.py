"""Shared blueprint contract helpers (IMP-0244 supporting artifact)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Contract:
    id: str
    required: tuple[str, ...] = ()
