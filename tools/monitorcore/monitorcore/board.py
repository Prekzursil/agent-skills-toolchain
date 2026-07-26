"""``board`` — the pure fixed-size frame-assembly substrate for the cockpit (WU0).

Turns a sequence of ANSI-FREE row strings into a FIXED ``height`` × ``cols`` frame —
every row clipped/padded to the column width, the block clipped/padded to the row
height — so :func:`monitorcore.ansi_screen.render_frame` can repaint a stable
rectangle each tick. The rows are ANSI-free by contract (monitorcore renders the
colour table separately from the text, like ``codex_tail`` / ``agent_tail``), so a
plain codepoint slice is a correct visible-width clip here; visible-width-aware
breakpoints for double-width glyphs are a later work unit (WU4). The module is
stdlib-only so it vendors cleanly into a skill's plain Python.
"""

from __future__ import annotations

from collections.abc import Sequence

__all__ = ["assemble_frame", "clip_cell"]


def clip_cell(text: str, cols: int) -> str:
    """Clip or space-pad an ANSI-free ``text`` to exactly ``cols`` codepoints."""
    if cols <= 0:
        return ""
    if len(text) > cols:
        return text[:cols]
    return text + " " * (cols - len(text))


def assemble_frame(rows: Sequence[str], cols: int, height: int) -> tuple[str, ...]:
    """A fixed ``height`` × ``cols`` frame: rows clipped/padded, block padded blank.

    Rows beyond ``height`` are dropped; a short frame is padded with blank lines so
    the repainted rectangle is always exactly ``height`` lines. ``height <= 0``
    yields an empty frame.
    """
    if height <= 0:
        return ()
    lines = [clip_cell(row, cols) for row in list(rows)[:height]]
    blank = clip_cell("", cols)
    while len(lines) < height:
        lines.append(blank)
    return tuple(lines)
