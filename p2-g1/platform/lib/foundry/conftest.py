"""Make ``import foundry`` / ``import wfdsl`` resolve no matter where pytest is invoked from.

Mirrors ``platform/lib/wfdsl/conftest.py``: ``platform/lib`` goes on ``sys.path`` so both
packages resolve by their own name. We deliberately do NOT put the repo ROOT on ``sys.path``
and there is deliberately no ``platform/__init__.py`` - that would turn the build root into a
real package named ``platform`` and shadow the standard library module of the same name.
"""

from __future__ import annotations

import sys
from pathlib import Path

LIB_ROOT = Path(__file__).resolve().parents[1]
if str(LIB_ROOT) not in sys.path:
    sys.path.insert(0, str(LIB_ROOT))
