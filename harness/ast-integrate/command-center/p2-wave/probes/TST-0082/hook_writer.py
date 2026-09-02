#!/usr/bin/env python3
"""Observable hook body: write one RECEIPT line when a client actually executes us.

Registration in hooks.json is not this file running. The dispatcher must
subprocess-exec this script; the line records the child pid so an in-process
forgery cannot satisfy the probe.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path


def main() -> int:
    receipt = os.environ.get("TST0082_RECEIPT") or ""
    if not receipt:
        print("FAILED:hook_writer TST0082_RECEIPT is unset", file=sys.stderr)
        return 2
    if len(sys.argv) < 3:
        print("FAILED:hook_writer usage hook_writer.py <EventName> <hook_id>", file=sys.stderr)
        return 2
    event = sys.argv[1]
    hook_id = sys.argv[2]
    path = Path(receipt)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = (
        f"RECEIPT event={event} hook_id={hook_id} "
        f"pid={os.getpid()} ppid={os.getppid()} ts={time.time_ns()}\n"
    )
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(line)
        handle.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
