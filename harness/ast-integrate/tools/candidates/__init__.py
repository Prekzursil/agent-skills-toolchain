"""Candidate evidence package."""
from __future__ import annotations

import importlib.util
from pathlib import Path

_IMP0165 = (
    Path(__file__).resolve().parents[2]
    / "command-center"
    / "p2-wave"
    / "probes"
    / "IMP-0165"
    / "candidates.py"
)
CANDIDATES = []
UNKNOWN = "UNKNOWN"


def labelled_stats():
    return {"total": 0, "unknown": 0, "known": 0, "rate": 0.0, "candidate_count": 0}


if _IMP0165.is_file():
    spec = importlib.util.spec_from_file_location("imp0165_candidates", _IMP0165)
    if spec and spec.loader:
        _mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_mod)
        CANDIDATES = list(getattr(_mod, "CANDIDATES", []))
        UNKNOWN = getattr(_mod, "UNKNOWN", UNKNOWN)
        labelled_stats = _mod.labelled_stats  # type: ignore[assignment]
