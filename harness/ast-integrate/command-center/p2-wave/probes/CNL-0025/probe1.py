#!/usr/bin/env python3
"""Thin alias so the measure fallback can find probe1*.py."""
from probe1_both_states import main

if __name__ == "__main__":
    raise SystemExit(main())
