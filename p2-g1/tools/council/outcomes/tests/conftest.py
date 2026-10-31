"""Path setup for the directly-runnable IMP-0356 test module."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
for p in (
    str(REPO / "tools"),
    str(REPO / "command-center/p2-wave/probes/IMP-0356"),
):
    if p not in sys.path:
        sys.path.insert(0, p)
