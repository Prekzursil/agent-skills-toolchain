#!/usr/bin/env python3
"""Thin alias so glob probe1*.py still finds a short name."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe1_live_matrix import main

if __name__ == "__main__":
    raise SystemExit(main())
