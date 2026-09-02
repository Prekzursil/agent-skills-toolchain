#!/usr/bin/env python3
"""No-op PostToolUse hook: always OK / exit 0 regardless of tool or HTTP status."""
from __future__ import annotations

import json
import sys


def main() -> int:
    json.load(sys.stdin)
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
