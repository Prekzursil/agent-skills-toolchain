#!/usr/bin/env python3
"""Stdio stand-in for an MCP mount: print ready, then wait for SIGTERM."""
from __future__ import annotations

import signal
import sys
import time


def _stop(*_args) -> None:
    raise SystemExit(0)


def main() -> int:
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    name = sys.argv[1] if len(sys.argv) > 1 else "mcp.unnamed"
    sys.stdout.write(f"ready {name}\n")
    sys.stdout.flush()
    while True:
        time.sleep(0.25)


if __name__ == "__main__":
    raise SystemExit(main())
