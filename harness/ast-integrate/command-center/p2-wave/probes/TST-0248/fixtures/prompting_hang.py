#!/usr/bin/env python3
"""Deliberately prompting command for the hang-bound detector control.

input() against /dev/null raises EOFError immediately, so it would NOT
exercise a wall-clock hang bound. This fixture prints a prompt and then
blocks on a private pipe whose write end stays open — the read cannot be
satisfied by stdin=DEVNULL, which is the planted wait the bound must catch.
"""
from __future__ import annotations

import os
import sys


def main() -> int:
    sys.stderr.write("Enter passphrase: ")
    sys.stderr.flush()
    read_fd, write_fd = os.pipe()
    # Keep write_fd open so the read waits forever (no EOF).
    os.read(read_fd, 1)
    os.close(write_fd)
    os.close(read_fd)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
