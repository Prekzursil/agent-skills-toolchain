"""Shared paths for IMP-0195 probes."""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXDIR = HERE / "fixtures"
AGENTSPEC_ROOT = REPO / "tools" / "agentspec"

if str(AGENTSPEC_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENTSPEC_ROOT))
