"""Import surface for probes. Adds hooks/_shared to sys.path."""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
SHARED = REPO / "hooks" / "_shared"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))

from session_keyed_store import (  # noqa: E402
    KEY_SHAPE_PROJECT,
    KEY_SHAPE_SESSION,
    KEY_TEMPLATE_PROJECT,
    KEY_TEMPLATE_SESSION,
    SessionKeyedStore,
    make_key,
)

__all__ = [
    "KEY_SHAPE_PROJECT",
    "KEY_SHAPE_SESSION",
    "KEY_TEMPLATE_PROJECT",
    "KEY_TEMPLATE_SESSION",
    "REPO",
    "SessionKeyedStore",
    "make_key",
]
