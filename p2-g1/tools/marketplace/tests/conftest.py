"""Bootstrap sys.path so marketplace tests run standalone (python -B <file>)."""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
for p in (str(REPO / "tools" / "marketplace"), str(REPO / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)
