"""Make ``import routing`` work no matter where pytest is invoked from.

``platform`` is prepended to ``sys.path`` so this package resolves by its own name,
exactly as ``platform/lib/wfdsl/conftest.py`` does for ``wfdsl``. There is deliberately
NO ``platform/__init__.py``: the stdlib ``platform`` module always outranks a namespace
package, so creating one would shadow the standard library rather than expose this tree.
Probed on this box -- with the repo ROOT on ``sys.path``, ``import platform`` still
resolves to the stdlib, which is why the package is addressed as ``routing`` and never
as ``platform.routing``.
"""

from __future__ import annotations

import sys
from pathlib import Path

BUILD_ROOT = Path(__file__).resolve().parents[1]
if str(BUILD_ROOT) not in sys.path:
    sys.path.insert(0, str(BUILD_ROOT))
