#!/usr/bin/env python3
"""Python longrun entrypoint — reports the resolved interpreter path."""
from __future__ import annotations

import sys


def main() -> int:
    print(f"interpreter={sys.executable}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
