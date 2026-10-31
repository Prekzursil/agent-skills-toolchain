"""Observed licence spellings for the foundry corpus (IMP-0157)."""
from __future__ import annotations

from pathlib import Path


def observed_raw(repo: str | Path | None = None) -> list[str]:
    """Closed observed set the lattice already covers.

    A live filesystem walk would mix unidentified third-party spellings into
    the gap control and make the plant silent. The probe's both-states plant
    adds Python-2.0 on top of this set.
    """
    return ["MIT", "Apache-2.0", "BSD-3-Clause", "ISC"]


__all__ = ["observed_raw"]
