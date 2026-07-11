"""Make the codex-fleet-github dir importable during tests.

The runtime scripts (server.py) add their own dir to sys.path; the tests import
``fleet_core`` directly, so mirror that here -- pytest loads this conftest before
collecting the test modules.
"""

import os
import sys

_TESTS = os.path.dirname(os.path.abspath(__file__))
_PKG = os.path.dirname(_TESTS)
if _PKG not in sys.path:
    sys.path.insert(0, _PKG)
