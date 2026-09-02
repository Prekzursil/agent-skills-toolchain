#!/usr/bin/env python3
"""Thin alias; prefer probe1_canary_sweep.py in named_probes."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe1_canary_sweep import main

if __name__ == "__main__":
    raise SystemExit(main())
