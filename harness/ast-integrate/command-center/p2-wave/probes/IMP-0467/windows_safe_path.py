"""Re-export the real path library used by IMP-0467 probes."""
from __future__ import annotations

import importlib.util
from pathlib import Path

_LIB = Path(__file__).resolve().parents[3] / "lib" / "windows_safe_path.py"
if not _LIB.is_file():
    raise ImportError(f"missing {_LIB}")
_spec = importlib.util.spec_from_file_location("_wsp_lib", _LIB)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)
globals().update({k: getattr(_mod, k) for k in dir(_mod) if not k.startswith("_")})
