"""Put the hub dir on sys.path so tests import server/backends/schema flatly."""

import os
import sys

_HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _HUB not in sys.path:
    sys.path.insert(0, _HUB)
