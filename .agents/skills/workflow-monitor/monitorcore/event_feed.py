"""``event_feed`` — pure ASCII event-feed rows over a thread's ``deque[ToolEvent]`` (WU2).

Renders the progress ledger monitorcore already captures (``CodexThread.events``, a
``deque[ToolEvent]`` folded at ingest by :mod:`monitorcore.codex_tail`) into ANSI-free,
width-clipped rows for the cockpit frame. The renderer is PURE: it consumes an
already-scrubbed, already-typed event model and never reads a file, a clock, or the
terminal, so it reaches 100% line+branch under injected inputs.

Glyphs are deliberately **ASCII width-1** (``$ * + > ~`` for the event ``kind``, ``. o x``
for the ``status``) — not double-width emoji-presentation glyphs, which corrupt column
alignment on Windows Terminal. Each free-text field (``label`` / ``detail``) was scrubbed
by the parser that built the event, so this module only formats and clips; the event's
own duration is shown when the source reported one, and a deterministic UTC ``HH:MM:SS``
stamp is derived from the event's ``ts`` (never the wall clock, so a frame is byte-stable).

:func:`thread_rows` is the "interleave into the frame rows" primitive: a thread's board
line followed — when expanded — by its most-recent event rows, indented one level deeper,
so the fleet → group → thread → **event** containment tree renders as a flat row list the
:mod:`monitorcore.board` assembler can frame. The module is stdlib-only so it vendors
cleanly into a skill's plain Python.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone

from .codex_tail import CodexThread, ToolEvent, board_line, clip, fmt_dur

__all__ = [
    "event_glyph",
    "event_row",
    "event_rows",
    "kind_glyph",
    "status_glyph",
    "thread_rows",
]

# ASCII width-1 glyphs (no double-width emoji — see the module docstring).
_KIND_GLYPH = {"cmd": "$", "tool": "*", "patch": "+", "msg": ">", "think": "~"}
_STATUS_GLYPH = {"running": ".", "ok": "o", "error": "x", "": " "}
_UNKNOWN = "?"

_THREAD_INDENT = "    "  # a thread sits one level under its group header
_EVENT_INDENT = "      "  # an event sits one level under its thread line


def kind_glyph(kind: str) -> str:
    """The ASCII glyph for an event ``kind`` (``?`` for an unknown kind)."""
    return _KIND_GLYPH.get(kind, _UNKNOWN)


def status_glyph(status: str) -> str:
    """The ASCII glyph for an event ``status`` (``?`` for an unknown status)."""
    return _STATUS_GLYPH.get(status, _UNKNOWN)


def event_glyph(ev: ToolEvent) -> str:
    """A 2-char ASCII glyph: the kind marker followed by the status marker."""
    return kind_glyph(ev.kind) + status_glyph(ev.status)


def _hms(ts: float) -> str:
    """A deterministic UTC ``HH:MM:SS`` for ``ts`` (``--:--:--`` when unknown)."""
    if ts <= 0:
        return "--:--:--"
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%H:%M:%S")


def event_row(ev: ToolEvent, width: int) -> str:
    """One clipped ANSI-free feed row for ``ev`` (its text is already scrubbed).

    ``<HH:MM:SS> <kind><status> <label>[: <detail>][ (<dur>)]`` — the label is dropped
    when empty (a detail-only event shows just its detail); a bare event with neither
    shows only its glyph; the duration is appended only when the source reported one.
    """
    text = ev.label
    if ev.detail:
        text = f"{text}: {ev.detail}" if text else ev.detail
    body = f"{event_glyph(ev)} {text}" if text else event_glyph(ev)
    if ev.dur is not None:
        body = f"{body} ({fmt_dur(ev.dur)})"
    return clip(f"{_hms(ev.ts)} {body}", width)


def _tail(items: list[ToolEvent], limit: int | None) -> list[ToolEvent]:
    """The most-recent ``limit`` items (``None`` = all; ``<= 0`` = none)."""
    if limit is None:
        return items
    if limit <= 0:
        return []
    return items[-limit:]


def event_rows(
    events: Iterable[ToolEvent],
    width: int,
    *,
    limit: int | None = None,
    indent: str = "",
) -> list[str]:
    """Clipped rows for the most-recent ``limit`` events, in chronological order.

    ``limit=None`` renders every event; ``limit <= 0`` renders none. Each row is
    prefixed with ``indent`` and its content clipped to the remaining width.
    """
    inner = max(0, width - len(indent))
    return [indent + event_row(ev, inner) for ev in _tail(list(events), limit)]


def thread_rows(
    th: CodexThread,
    now: float,
    width: int,
    *,
    show_events: bool = False,
    event_limit: int | None = None,
    indent: str = _THREAD_INDENT,
    event_indent: str = _EVENT_INDENT,
) -> list[str]:
    """A thread's board line, then — when ``show_events`` — its recent event feed.

    The board line is indented one level (under a group header) and clipped to the
    remaining width; the interleaved event rows are indented one level deeper.
    """
    inner = max(0, width - len(indent))
    rows = [indent + clip(board_line(th, now), inner)]
    if show_events:
        rows.extend(
            event_rows(th.events, width, limit=event_limit, indent=event_indent)
        )
    return rows
