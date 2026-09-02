#!/usr/bin/env python3
"""Thin alias so glob probe2*.py still finds a short name."""
from probe2_property_and_unjittered import main

if __name__ == "__main__":
    raise SystemExit(main())
