"""Make ``import mkt`` resolve no matter where pytest is invoked from.

Mirrors ``platform/lib/wfdsl/conftest.py``: the PARENT of the package goes on
``sys.path`` so the package resolves by its own name. We deliberately do NOT put the repo
root on ``sys.path`` and there is deliberately no ``platform/__init__.py`` -- that would
turn the build root into a real package named ``platform`` and shadow the standard library
module of the same name.
"""

from __future__ import annotations

import sys
from pathlib import Path

MARKETPLACE_ROOT = Path(__file__).resolve().parents[1]
if str(MARKETPLACE_ROOT) not in sys.path:
    sys.path.insert(0, str(MARKETPLACE_ROOT))
