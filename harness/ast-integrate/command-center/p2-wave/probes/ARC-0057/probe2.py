#!/usr/bin/env python3
"""Thin alias so glob probe2*.py still finds a short name."""
from probe2_skip_accounting import main

if __name__ == "__main__":
    raise SystemExit(main())
