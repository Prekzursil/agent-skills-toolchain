"""Background worker: burn CPU and append bytes."""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path


def main() -> int:
    root = Path(sys.argv[1])
    cpu = root / "cpu.counter"
    log = root / "artifact.log"
    root.mkdir(parents=True, exist_ok=True)
    n = 0
    while True:
        n += 1
        cpu.write_text(str(n), encoding="utf-8")
        with log.open("ab") as fh:
            fh.write(b"x" * 64)
        # burn a little CPU
        acc = 0
        for i in range(20000):
            acc += i * i
        time.sleep(0.05)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
