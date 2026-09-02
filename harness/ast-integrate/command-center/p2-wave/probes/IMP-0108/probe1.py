#!/usr/bin/env python3
"""Thin alias so a measure that globs probe1*.py still hits the named probe."""
from probe1_manifest_matches import main

if __name__ == "__main__":
    raise SystemExit(main())
