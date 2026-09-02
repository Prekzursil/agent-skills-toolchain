#!/usr/bin/env python3
"""Thin alias so a measure that glob's probe1*.py still hits the named probe."""
from probe1_counting_invariance import main

if __name__ == "__main__":
    raise SystemExit(main())
