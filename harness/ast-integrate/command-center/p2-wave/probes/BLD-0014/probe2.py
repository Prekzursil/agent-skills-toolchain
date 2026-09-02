#!/usr/bin/env python3
"""Thin alias so a measure that globs probe2*.py still hits the named probe."""
from probe2_ci_and_review import main

if __name__ == "__main__":
    raise SystemExit(main())
