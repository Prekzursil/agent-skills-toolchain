#!/usr/bin/env python3
# ASSERTION: cell windows__macos-zsh (Windows x macOS zsh) ships as a runnable probe.
# Absent platforms report NOT-CHECKED, never PASS.
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cell_runtime import main_cell  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main_cell('windows__macos-zsh', 'Windows', 'macOS zsh'))
