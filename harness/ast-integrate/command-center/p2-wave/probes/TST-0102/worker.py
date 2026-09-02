#!/usr/bin/env python3
"""Long-lived tagged child. Argv is the process-table census surface."""
from __future__ import annotations

import signal
import time


def _term(_signum: int, _frame: object) -> None:
    raise SystemExit(0)


def main() -> int:
    signal.signal(signal.SIGTERM, _term)
    signal.signal(signal.SIGINT, _term)
    while True:
        time.sleep(1.0)


if __name__ == "__main__":
    raise SystemExit(main())
