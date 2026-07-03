"""Make the hub dir and the shared module dir importable during tests.

``accounts.py`` is shared across hubs and lives in ``tools/mcp/_shared``. The
runtime ``hub.py``/``backends.py`` add it to ``sys.path`` themselves, but the
tests import those modules directly, so mirror that here -- pytest loads this
conftest before collecting the test modules.
"""
import os
import sys

_TESTS = os.path.dirname(os.path.abspath(__file__))
_HUB = os.path.dirname(_TESTS)
_SHARED = os.path.join(os.path.dirname(_HUB), "_shared")
for _p in (_HUB, _SHARED):
    if _p not in sys.path:
        sys.path.insert(0, _p)
