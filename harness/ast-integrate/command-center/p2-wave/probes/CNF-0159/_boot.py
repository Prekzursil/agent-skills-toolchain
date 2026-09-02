"""Shared import bootstrap for CNF-0159 probes."""
from __future__ import annotations

import sys
from pathlib import Path

PROBE_DIR = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
PKG_PARENT = REPO / "command-center" / "confirmation"


def import_pkg():
    if str(PKG_PARENT) not in sys.path:
        sys.path.insert(0, str(PKG_PARENT))
    import dispatch_integrity as di  # noqa: WPS433

    return di
