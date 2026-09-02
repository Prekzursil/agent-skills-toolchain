#!/usr/bin/env python3
# ASSERTION: cell linux__cmd.exe (Linux x cmd.exe) ships as a runnable probe.
# Absent platforms report NOT-CHECKED, never PASS.
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cell_runtime import main_cell  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main_cell('linux__cmd.exe', 'Linux', 'cmd.exe'))
