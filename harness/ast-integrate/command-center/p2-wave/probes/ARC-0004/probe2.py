#!/usr/bin/env python3
"""Thin alias so a measure that globs probe2*.py still hits the named probe."""
from probe2_remeasure_crossover import main

if __name__ == "__main__":
    raise SystemExit(main())
