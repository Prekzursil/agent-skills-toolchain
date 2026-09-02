#!/usr/bin/env python3
"""Non-specific detector: fires on every component (environment, not defect).

Planted so the matrix can quarantine a repro that is red on healthy components.
Exit 2 always.
"""
from __future__ import annotations

import sys


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: repro_nonspecific.py <component-dir>", file=sys.stderr)
        return 2
    print("FIRE environment (non-specific)")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
