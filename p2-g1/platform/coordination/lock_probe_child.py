"""Child half of the OS-lock liveness control: take an exclusive lock, signal, then wait.

Not a test and not scratch - it is a tracked helper that ``test_oslock.py`` and
``liveness_control.py`` both spawn as a REAL separate process. The control is only meaningful
across a process boundary: the whole claim being verified is that the OPERATING SYSTEM releases
the lock when the holder exits, which cannot be exercised inside one interpreter.

argv: ``<lock_path> <ready_path> <hold_seconds>``
Writes ``LOCK-HELD pid=<n>`` (or ``LOCK-REFUSED <errno>``) to ``ready_path`` so the parent can
synchronise without polling a timeout it has to guess.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE.parent) not in sys.path:
    sys.path.insert(0, str(HERE.parent))

from coordination.oslock import LivenessLock  # noqa: E402  - after the sys.path fix above


def main(argv: list[str]) -> int:
    lock_path, ready_path, hold = argv[1], argv[2], float(argv[3])
    lock = LivenessLock(lock_path)
    acquired = lock.acquire()
    Path(ready_path).write_text(
        f"LOCK-HELD pid={os.getpid()}" if acquired else "LOCK-REFUSED",
        encoding="utf-8",
    )
    if not acquired:
        return 3
    time.sleep(hold)
    lock.release()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
