"""Put the lane directory on sys.path so the tests import the guard as a sibling module.

`command-center` contains a hyphen and so can never be a package; the same conftest trick is
what `tools/command-center/tests` uses.
"""

from __future__ import annotations

import sys
from pathlib import Path

LANE = Path(__file__).resolve().parents[1]
if str(LANE) not in sys.path:
    sys.path.insert(0, str(LANE))
