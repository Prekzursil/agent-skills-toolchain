"""Package agentspec.

G-1 PYTHONPATH includes both ``tools/`` and ``tools/agentspec``. Importing
``agentspec`` via ``tools/`` would otherwise bind this directory (no spec.py)
and hide ``tools/agentspec/agentspec/spec.py``. Prefer the inner package path.
"""

from __future__ import annotations

from pathlib import Path

_HERE = Path(__file__).resolve().parent
_INNER = _HERE / "agentspec"
__path__ = [str(_INNER), str(_HERE)]

SPEC_VERSION = "1"
