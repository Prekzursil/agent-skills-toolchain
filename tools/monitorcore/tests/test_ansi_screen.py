"""Tests for ``monitorcore.ansi_screen`` — the alt-screen + synchronized-output
full-repaint substrate (WU7), 100% line+branch.

The pure escape-sequence builders are asserted against their exact bytes; the thin
terminal I/O shell (``stdout``) is ``# pragma: no cover`` (it binds the real
terminal). ``terminal_size`` (via an injected size-getter) and ``paint`` (via an
in-memory buffer) are exercised without driving a TTY, so both cover their branches.
"""

from __future__ import annotations

import io
import os

from monitorcore import ansi_screen as scr

_ESC = "\x1b"


def test_control_constants_are_exact_bytes():
    assert scr.ALT_ENTER == f"{_ESC}[?1049h"
    assert scr.ALT_LEAVE == f"{_ESC}[?1049l"
    assert scr.HIDE_CURSOR == f"{_ESC}[?25l"
    assert scr.SHOW_CURSOR == f"{_ESC}[?25h"
    assert scr.SYNC_BEGIN == f"{_ESC}[?2026h"
    assert scr.SYNC_END == f"{_ESC}[?2026l"
    assert scr.HOME == f"{_ESC}[H"
    assert scr.CLEAR_ALL == f"{_ESC}[2J"
    assert scr.CLEAR_EOL == f"{_ESC}[K"
    assert scr.CLEAR_EOS == f"{_ESC}[J"


def test_enter_screen_switches_buffer_hides_cursor_and_clears():
    assert scr.enter_screen() == (
        scr.ALT_ENTER + scr.HIDE_CURSOR + scr.HOME + scr.CLEAR_ALL
    )


def test_leave_screen_restores_cursor_and_primary_buffer():
    assert scr.leave_screen() == scr.SHOW_CURSOR + scr.ALT_LEAVE


def test_render_frame_wraps_lines_in_a_synchronized_full_repaint():
    payload = scr.render_frame(["a", "bb"])
    assert payload == (
        scr.SYNC_BEGIN
        + scr.HOME
        + f"a{scr.CLEAR_EOL}\r\nbb{scr.CLEAR_EOL}"
        + scr.CLEAR_EOS
        + scr.SYNC_END
    )


def test_render_frame_empty_is_a_valid_blank_synchronized_frame():
    # the genexpr must also cover the zero-iteration (empty) branch
    assert scr.render_frame([]) == (
        scr.SYNC_BEGIN + scr.HOME + "" + scr.CLEAR_EOS + scr.SYNC_END
    )


def test_paint_writes_payload_and_flushes_the_injected_stream():
    flushed: list[bool] = []
    buf = io.StringIO()
    orig_flush = buf.flush

    def _track_flush() -> None:
        flushed.append(True)
        orig_flush()

    buf.flush = _track_flush  # type: ignore[method-assign]
    scr.paint("XYZ", buf)
    assert buf.getvalue() == "XYZ"
    assert flushed == [True]


def test_terminal_size_returns_columns_and_lines():
    fake = os.terminal_size((132, 43))
    assert scr.terminal_size(getsize=lambda: fake) == (132, 43)


def test_terminal_size_falls_back_on_oserror():
    def boom() -> os.terminal_size:
        raise OSError("not a terminal")

    assert scr.terminal_size((100, 30), getsize=boom) == (100, 30)
