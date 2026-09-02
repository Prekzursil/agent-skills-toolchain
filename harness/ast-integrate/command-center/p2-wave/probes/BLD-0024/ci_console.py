#!/usr/bin/env python3
"""CI console-script entry point (the runner Phase 0 baseline did NOT use).

Invoked as a file path, not `python -m pytest`. sys.path starts at the fake
installed layout so in-tree-only helpers are invisible — that is the packaging
gap the baseline detector could not see.
"""
from __future__ import annotations

import sys
from pathlib import Path

INSTALLED = Path(__file__).resolve().parent / "fixtures" / "installed"
# Console-script convention: the wrapper's directory layout is the install root.
sys.path.insert(0, str(INSTALLED))

from bld0024_ci.runner import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
