"""Probe-local import of the shipped degradation event surface."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools" / "command-center"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import degradation_events as D  # noqa: E402

USER_EVENTS = D.USER_EVENTS
DEBUG_EVENTS = D.DEBUG_EVENTS
USER_EVENTS = USER_EVENTS
DEBUG_EVENTS = DEBUG_EVENTS
reset = D.reset
emit_loud = D.emit_loud
emit_debug = D.emit_debug
