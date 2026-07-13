"""Source-neutral terminal loop for launchable :class:`MonitorSource` adapters.

The launcher chooses an adapter-specific entry script; that script constructs its source and
hands it here.  This module owns the shared ``poll -> render_native -> redraw`` lifecycle so a
new adapter does not grow another monitor engine.  Output and sleeping are injectable, keeping
the loop deterministic and fully testable without a real terminal or delay.
"""

from __future__ import annotations

import sys
import time
from collections.abc import Callable
from typing import TextIO, TypeVar

from .contract import MonitorSource

__all__ = ["run"]

P = TypeVar("P")
_CLEAR = "\x1b[2J\x1b[H"


def run(
    source: MonitorSource[P],
    *,
    interval: float = 1.0,
    once: bool = False,
    out: TextIO | None = None,
    sleeper: Callable[[float], object] = time.sleep,
) -> int:
    """Poll and render ``source`` once or until interrupted.

    ``once`` deliberately omits terminal-control bytes so snapshots are pipe- and test-friendly.
    Continuous mode redraws the same terminal and exits cleanly on ``KeyboardInterrupt``.
    """
    stream = sys.stdout if out is None else out
    try:
        while True:
            snap = source.poll()
            if not once:
                stream.write(_CLEAR)
            stream.write(f"{source.render_native(snap)}\n")
            stream.flush()
            if once:
                return 0
            sleeper(interval)
    except KeyboardInterrupt:
        return 0
