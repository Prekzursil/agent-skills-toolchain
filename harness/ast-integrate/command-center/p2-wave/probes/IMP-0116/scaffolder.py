"""Probe-local re-export of marketplace scaffolder."""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "marketplace"))

from scaffolder import KINDS, scaffold  # noqa: E402

__all__ = ["KINDS", "scaffold"]
