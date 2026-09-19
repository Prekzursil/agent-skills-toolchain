#!/usr/bin/env python3
"""CC-0006 build entry — delegates to probes/CC-0006/_pack_receipt.py."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

PACK = Path(__file__).resolve().parent / "probes" / "CC-0006" / "_pack_receipt.py"

if __name__ == "__main__":
    sys.argv[0] = str(PACK)
    runpy.run_path(str(PACK), run_name="__main__")
