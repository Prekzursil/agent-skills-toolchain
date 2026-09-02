#!/usr/bin/env python3
"""Thin alias so a measure that globs probe1*.py still hits the named probe."""
from probe1_untampered_and_append_only import main

if __name__ == "__main__":
    raise SystemExit(main())
