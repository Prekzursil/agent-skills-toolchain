from __future__ import annotations

import sys
from pathlib import Path


AGENTS_ROOT = Path(__file__).resolve().parents[2]
if str(AGENTS_ROOT) not in sys.path:  # pragma: no cover
    sys.path.insert(0, str(AGENTS_ROOT))
