#!/usr/bin/env python3
"""In-tree python -m style runner (the Phase 0 baseline class)."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "fixtures" / "pymodule_path"))

from revalidate import run_worker  # noqa: E402

if __name__ == "__main__":
    cond = sys.argv[1] if len(sys.argv) > 1 else "as_is"
    raise SystemExit(run_worker(["pymodule", cond]))
