#!/usr/bin/env python3
"""Thin alias so glob probe1*.py still finds a short name."""
from probe1_discovery_count import main

if __name__ == "__main__":
    raise SystemExit(main())
