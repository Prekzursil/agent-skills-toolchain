"""Re-export of :mod:`tools/command-center/work_unit_conformance` (the real module).

``command-center`` is not an importable package name, so the checker is
loaded by path and every public name is re-exported unchanged.
"""

from __future__ import annotations

import importlib.util as _ilu
import sys as _sys
from pathlib import Path as _Path

_REAL = _Path(__file__).resolve().parent / "command-center" / "work_unit_conformance.py"
if str(_REAL.parent) not in _sys.path:
    _sys.path.insert(0, str(_REAL.parent))
_spec = _ilu.spec_from_file_location("_work_unit_conformance_real", _REAL)
if _spec is None or _spec.loader is None:  # pragma: no cover - tree damage
    raise ImportError(f"cannot load {_REAL}")
_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
globals().update({k: v for k, v in vars(_mod).items() if not k.startswith("__")})
__all__ = [k for k in vars(_mod) if not k.startswith("_")]
