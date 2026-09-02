"""Make ``import wfdsl`` work no matter where pytest is invoked from.

``platform/lib`` is prepended to ``sys.path`` so the package resolves by its own name. NOTE:
we deliberately do NOT put the repo ROOT on ``sys.path`` and there is deliberately no
``platform/__init__.py`` - a regular stdlib module always outranks a namespace package, but
adding ``platform/__init__.py`` would turn the build root into a real package named
``platform`` and shadow the standard library. Probed on this box: with the repo root on
``sys.path``, ``import platform`` still resolves to ``C:/Python314/Lib/platform.py``.
"""

from __future__ import annotations

import sys
from pathlib import Path

LIB_ROOT = Path(__file__).resolve().parents[1]
if str(LIB_ROOT) not in sys.path:
    sys.path.insert(0, str(LIB_ROOT))
