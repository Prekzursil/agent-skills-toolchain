#!/usr/bin/env python3
"""List mirror-only entries directly under each probe dir (stale wave leftovers).

Runs on WSL. Compares ~/p2-g1/command-center/p2-wave/probes/*/ with the
Windows repo via /mnt/c. Prints entries present on the mirror but absent on
Windows (excluding __pycache__ and runtime/scratch outputs probes create).
"""
from __future__ import annotations

import os
from pathlib import Path

MIR = Path.home() / "p2-g1" / "command-center" / "p2-wave" / "probes"
WIN = Path("/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/probes")
IGNORE = {"__pycache__", "runtime", "scratch", "last_run.json", ".pytest_cache"}

count = 0
for mdir in sorted(MIR.iterdir()):
    if not mdir.is_dir():
        continue
    wdir = WIN / mdir.name
    if not wdir.is_dir():
        print(f"PROBE-DIR-ONLY-ON-MIRROR {mdir.name}")
        count += 1
        continue
    try:
        wset = set(os.listdir(wdir))
    except OSError:
        continue
    for entry in sorted(os.listdir(mdir)):
        if entry in IGNORE:
            continue
        if entry not in wset:
            kind = "dir" if (mdir / entry).is_dir() else "file"
            print(f"STALE {mdir.name}/{entry} ({kind})")
            count += 1
print("total", count)
