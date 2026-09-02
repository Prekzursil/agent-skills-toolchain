#!/usr/bin/env python3
"""Known-present session stand-in for TST-0019.

The caller must put TST-0019-SESSION-MARKER on argv so the process table
row is distinguishable from this file path alone.
"""
from __future__ import annotations

import time


def main() -> None:
    time.sleep(120)


if __name__ == "__main__":
    main()
