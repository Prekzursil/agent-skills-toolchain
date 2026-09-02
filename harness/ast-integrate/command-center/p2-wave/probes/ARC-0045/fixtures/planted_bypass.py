#!/usr/bin/env python3
"""Deliberately unwired capability invocation.

The enumerator must find `side_door_activate` as a bypass (subprocess side
effect, no evaluate/require_grant) before a zero-bypass claim is accepted.
Not imported by production code.
"""
from __future__ import annotations

import subprocess
import sys


def side_door_activate(package: str) -> int:
    """Planted bypass: activates a package without crossing the A7 choke."""
    return subprocess.Popen(  # noqa: S603
        [sys.executable, "-c", "print(0)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).wait()
