#!/usr/bin/env python3
# ASSERTION: cell macos__powershell-7 (macOS x PowerShell 7) ships as a runnable probe.
# Absent platforms report NOT-CHECKED, never PASS.
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cell_runtime import main_cell  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main_cell('macos__powershell-7', 'macOS', 'PowerShell 7'))
