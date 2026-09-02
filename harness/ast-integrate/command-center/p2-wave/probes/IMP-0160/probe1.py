#!/usr/bin/env python3
"""Thin alias so _measure_one_delivered.py can fall back to probe1*.py."""
from probe1_roundtrip import main

if __name__ == "__main__":
    raise SystemExit(main())
