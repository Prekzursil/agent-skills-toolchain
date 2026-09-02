#!/usr/bin/env python3
"""Thin alias so glob probe2*.py still finds a short name."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe2_alias_roundtrip import main

if __name__ == "__main__":
    raise SystemExit(main())
