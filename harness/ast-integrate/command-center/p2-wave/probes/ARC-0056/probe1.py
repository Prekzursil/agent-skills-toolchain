#!/usr/bin/env python3
"""Thin alias so glob probe1*.py still finds a short name."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe1_totality import main

if __name__ == "__main__":
    raise SystemExit(main())
