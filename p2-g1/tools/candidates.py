"""Re-export IMP-0165 labelled candidates so probes that insert tools/ still resolve."""
from __future__ import annotations

import importlib.util
from pathlib import Path

_SRC = (
    Path(__file__).resolve().parents[1]
    / "command-center"
    / "p2-wave"
    / "probes"
    / "IMP-0165"
    / "candidates.py"
)
_spec = importlib.util.spec_from_file_location("imp0165_candidates", _SRC)
if _spec is None or _spec.loader is None:
    raise ImportError(f"cannot load {_SRC}")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
CANDIDATES = _mod.CANDIDATES
UNKNOWN = _mod.UNKNOWN
labelled_stats = _mod.labelled_stats
