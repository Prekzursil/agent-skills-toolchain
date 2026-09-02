#!/usr/bin/env python3
"""Hold exclusive flock on named files until SIGTERM — Windows share-none analogue."""
from __future__ import annotations

import fcntl
import os
import signal
import sys
import time


def main() -> int:
    paths = sys.argv[1:]
    if not paths:
        print("FAILED:client no paths", file=sys.stderr)
        return 2
    fds = []
    for p in paths:
        fd = os.open(p, os.O_RDWR)
        fcntl.flock(fd, fcntl.LOCK_EX)
        fds.append(fd)
    stop = {"flag": False}

    def _stop(signum, frame):  # noqa: ARG001
        stop["flag"] = True

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    sys.stdout.write(f"LOCKER_PID={os.getpid()}\nREADY\n")
    sys.stdout.flush()
    while not stop["flag"]:
        time.sleep(0.05)
    for fd in fds:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        except OSError:
            pass
        os.close(fd)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
