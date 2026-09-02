"""Shared probe paths for IMP-0122."""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

OUT_REL = "command-center/receipts/IMP-0122.json"
OUT = REPO / OUT_REL
SENTINEL = "SUCCESS:IMP-0122"
