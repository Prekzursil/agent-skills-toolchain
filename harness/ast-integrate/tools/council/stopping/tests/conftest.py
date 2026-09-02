"""pytest path shim: make ``council`` importable from tools/ when collected in place."""
from __future__ import annotations

import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[3]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
