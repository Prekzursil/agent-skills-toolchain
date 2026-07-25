"""``ansi_screen`` — the alt-screen + synchronized-output full-repaint substrate (WU7).

The cockpit repaints the WHOLE frame every tick. This module splits cleanly into
PURE escape-sequence *builders* (fully covered by asserting the exact byte strings)
and a THIN terminal I/O shell (:func:`stdout`) that binds the real terminal and is
marked ``# pragma: no cover`` — exactly as monitorcore's existing ctypes / syscall
dodges are. :func:`terminal_size` takes an injectable size-getter and :func:`paint`
takes an EXPLICIT stream, so their fallback and write+flush logic are exercised
against a stub / an in-memory buffer, never a live TTY.

A full repaint is wrapped in DEC private mode **2026** (synchronized output /
BSU–ESU): the terminal buffers the frame and swaps it atomically, so a whole-screen
redraw does not tear or flicker even on a slow link. A terminal that does not
understand 2026 ignores the private-mode toggles and still receives a correct (if
un-batched) full repaint. Per-line erase-to-EOL plus a trailing erase-to-EOS make
the repaint self-cleaning: a shorter line or a shorter frame wipes the previous
frame's leftovers without a blanking whole-screen clear each tick.

The module is stdlib-only (``os`` / ``sys``) so it vendors cleanly into a skill's
plain Python. It reads no input and classifies no state — it only turns prepared
frame LINES into the bytes a terminal draws.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable, Sequence
from typing import TextIO

__all__ = [
    "ALT_ENTER",
    "ALT_LEAVE",
    "CLEAR_ALL",
    "CLEAR_EOL",
    "CLEAR_EOS",
    "HIDE_CURSOR",
    "HOME",
    "SHOW_CURSOR",
    "SYNC_BEGIN",
    "SYNC_END",
    "enter_screen",
    "leave_screen",
    "paint",
    "render_frame",
    "stdout",
    "terminal_size",
]

_ESC = "\x1b"

ALT_ENTER = f"{_ESC}[?1049h"  # switch to the alternate screen buffer
ALT_LEAVE = f"{_ESC}[?1049l"  # restore the primary screen buffer
HIDE_CURSOR = f"{_ESC}[?25l"
SHOW_CURSOR = f"{_ESC}[?25h"
SYNC_BEGIN = f"{_ESC}[?2026h"  # begin synchronized update (DEC private mode 2026)
SYNC_END = f"{_ESC}[?2026l"  # end synchronized update
HOME = f"{_ESC}[H"  # cursor to row 1 / col 1
CLEAR_ALL = f"{_ESC}[2J"  # erase the whole screen
CLEAR_EOL = f"{_ESC}[K"  # erase from the cursor to end of line
CLEAR_EOS = f"{_ESC}[J"  # erase from the cursor to end of screen


def enter_screen() -> str:
    """Bytes to enter the cockpit: alt-screen on, cursor hidden, screen cleared home."""
    return f"{ALT_ENTER}{HIDE_CURSOR}{HOME}{CLEAR_ALL}"


def leave_screen() -> str:
    """Bytes to restore the terminal: cursor shown, primary screen buffer restored."""
    return f"{SHOW_CURSOR}{ALT_LEAVE}"


def render_frame(lines: Sequence[str]) -> str:
    """A synchronized FULL-REPAINT of ``lines`` from the top-left.

    Each line is followed by an erase-to-EOL (so a shorter line overwrites a longer
    previous one) and the frame ends with an erase-to-EOS (so a shorter frame wipes
    leftover rows). The whole payload is wrapped in the 2026 begin/end pair so the
    terminal swaps it atomically. An empty ``lines`` still yields a valid (blank)
    synchronized frame.
    """
    body = "\r\n".join(f"{line}{CLEAR_EOL}" for line in lines)
    return f"{SYNC_BEGIN}{HOME}{body}{CLEAR_EOS}{SYNC_END}"


def paint(payload: str, out: TextIO) -> None:
    """Write a prepared ``payload`` to an EXPLICIT stream and flush it.

    Pure with respect to the injected stream (tested against an in-memory buffer);
    the real-terminal binding is isolated in :func:`stdout` behind a no-cover pragma.
    """
    out.write(payload)
    out.flush()


def stdout() -> TextIO:  # pragma: no cover - binds the real terminal stream
    return sys.stdout


def terminal_size(
    fallback: tuple[int, int] = (80, 24),
    *,
    getsize: Callable[[], os.terminal_size] = os.get_terminal_size,
) -> tuple[int, int]:
    """Current ``(columns, lines)``, or ``fallback`` when the size query fails.

    ``getsize`` is an injectable seam (defaults to the real ``os.get_terminal_size``
    syscall) so both the success path and the ``OSError`` → ``fallback`` branch are
    covered against a stub, never a live TTY.
    """
    try:
        size = getsize()
    except OSError:
        return fallback
    return (size.columns, size.lines)
