#!/usr/bin/env python3
"""Thin alias so _measure_one_delivered.py can fall back to probe2*.py."""
from probe2_lossy_ledger import main

if __name__ == "__main__":
    raise SystemExit(main())
