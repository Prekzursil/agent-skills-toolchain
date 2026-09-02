"""Council toolkit. Submodules are imported on demand; do not shadow them."""
from __future__ import annotations

from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[1] / "council"
__path__ = [str(_HERE)]
if _ROOT.is_dir():
    __path__.append(str(_ROOT))

__all__ = ["charter", "conflicts", "antifail", "simulate", "topology"]
