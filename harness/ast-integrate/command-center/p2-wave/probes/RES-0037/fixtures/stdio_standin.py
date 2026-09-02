#!/usr/bin/env python3
"""Long-lived stdio MCP stand-in. Identity is argv[1], not this file path."""
from __future__ import annotations

import sys
import time


def main() -> int:
    if len(sys.argv) < 2:
        print("FAILED:stdio-standin missing token", file=sys.stderr)
        return 2
    while True:
        time.sleep(0.25)


if __name__ == "__main__":
    raise SystemExit(main())
