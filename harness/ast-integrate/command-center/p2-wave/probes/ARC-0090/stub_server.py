#!/usr/bin/env python3
"""Long-lived MCP stub for ARC-0090 process-table probes.

The mark token MUST be its own argv element so /proc cmdline and `ps`
can find this child without matching the parent probe.
"""
from __future__ import annotations

import argparse
import signal
import sys
import time


def _ignore_sigterm_until_kill(_signum: int, _frame: object) -> None:
    # Parent reaps with SIGTERM then SIGKILL. Stay listed until SIGKILL
    # only if we are mid-sleep; default SIGTERM is enough to exit.
    raise SystemExit(0)


def main() -> int:
    parser = argparse.ArgumentParser(prog="arc0090_stub_server.py")
    parser.add_argument("--arc0090-mark", required=True)
    parser.add_argument("--server-id", required=True)
    parser.add_argument("--mode", default="stdio", choices=("stdio", "http"))
    args = parser.parse_args()
    _ = (args.arc0090_mark, args.server_id, args.mode)
    signal.signal(signal.SIGTERM, _ignore_sigterm_until_kill)
    while True:
        time.sleep(1.0)


if __name__ == "__main__":
    raise SystemExit(main())
