"""Re-export the real agentrail.ports implementation."""
from __future__ import annotations

import importlib.util
from pathlib import Path

_REAL = Path(__file__).resolve().parents[2] / "agentrail" / "agentrail" / "ports.py"
import sys

_spec = importlib.util.spec_from_file_location("agentrail.ports", _REAL)
if _spec is None or _spec.loader is None:
    raise ImportError(str(_REAL))
_mod = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("agentrail.ports", _mod)
_spec.loader.exec_module(_mod)
globals().update({k: getattr(_mod, k) for k in dir(_mod) if not k.startswith("_")})
