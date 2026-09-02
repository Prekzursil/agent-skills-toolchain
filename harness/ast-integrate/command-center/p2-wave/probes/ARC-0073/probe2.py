#!/usr/bin/env python3
"""Thin alias so a measure that glob's probe2*.py still hits the named probe."""
from probe2_reviewer import main

if __name__ == "__main__":
    raise SystemExit(main())
