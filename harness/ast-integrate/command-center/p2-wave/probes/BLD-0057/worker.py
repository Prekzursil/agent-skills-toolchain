#!/usr/bin/env python3
"""Tagged BLD-0057 child: hold FDs and optional anonymous commit, then wait."""
from __future__ import annotations

import mmap
import os
import signal
import time
from pathlib import Path


def _term(_signum, _frame) -> None:
    raise SystemExit(0)


def main() -> int:
    signal.signal(signal.SIGTERM, _term)
    signal.signal(signal.SIGINT, _term)
    held = []
    for _ in range(int(os.environ.get("BLD0057_FDS", "4"))):
        held.append(open("/dev/null", "rb"))  # noqa: SIM115
    n = int(os.environ.get("BLD0057_MMAP", "0"))
    mapping = None
    if n > 0:
        mapping = mmap.mmap(-1, n)
        step = 4096
        for off in range(0, n, step):
            mapping[off] = 1
    beat = os.environ.get("BLD0057_HEARTBEAT")
    while True:
        if beat:
            try:
                Path(beat).write_text(str(os.getpid()), encoding="utf-8")
            except OSError:
                pass
        time.sleep(0.15)
    if mapping is not None:
        mapping.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
