#!/usr/bin/env python3
"""Thin alias so the measure fallback can find probe2*.py."""
from probe2_coverage_review import main

if __name__ == "__main__":
    raise SystemExit(main())
