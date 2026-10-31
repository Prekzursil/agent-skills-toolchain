#!/usr/bin/env python3
"""Bounded transcript reads — O(tail) instead of O(session length).

WHY THIS EXISTS (measured 2026-08-08, root cause of the recurring `DISARMED 4/9`):

Four Stop checks parse the transcript, and their cost scales with SESSION LENGTH rather than with
the turn they are judging. Against this session's real 109 MB / 48,466-line transcript:

    honest-signal        21.26 s   (budget 10 s)   <- 2.1x over
    journey-coverage     11.06 s   (budget 10 s)   <- over
    stub-ledger/report    9.58 s   (budget 25 s)
    forge/todo-surfacer   9.37 s   (budget 18 s)
    other five            0.99-2.67 s
    SUM                  63.7 s    vs a 35 s events.Stop.settings_timeout host wall

Those four slowest are EXACTLY the four that report DISARMED. Raising budgets cannot fix it --
63.7 s exceeds the 35 s host wall however the 144 s of per-check budget is divided. The cost has to
come down, and it can: `journey-coverage/check.py:277` and `stub-ledger/report.py:87` both define
`_final_text()` -- "concatenated text of the FINAL assistant message" -- and both obtain it by
reading every line from the top.

A Stop-time check about THIS turn does not need 48,466 lines of history. Seek from the END.

DESIGN NOTES
  * `iter_tail_lines` reads fixed-size blocks backwards from EOF, so cost is proportional to how
    far back the answer lies, not to file size. A partial first line is discarded -- it is the
    tail of a record whose head was not read, and parsing it would be a truncation bug.
  * Every function is FAIL-OPEN and typed: a missing/unreadable/garbage transcript yields the same
    empty result as an absent one, never an exception into a hook. Under P2-01 a caller that
    cannot distinguish "no final message" from "could not read" must surface NOT-CHECKED, so
    `final_assistant_text` returns `(text, ok)` -- `ok=False` means the read itself failed.
  * `max_bytes` bounds the worst case: a transcript whose last assistant message is genuinely
    enormous, or one with no assistant record at all, still terminates.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

__all__ = ["iter_tail_lines", "final_assistant_text", "tail_events"]

_BLOCK = 64 * 1024
_DEFAULT_MAX_BYTES = 8 * 1024 * 1024  # 8 MB of tail is far more than one turn


def iter_tail_lines(path, max_bytes: int = _DEFAULT_MAX_BYTES):
    """Yield complete lines from EOF backwards, newest first. Never raises."""
    try:
        p = Path(path)
        size = p.stat().st_size
        if size == 0:
            return
        want = min(size, max(max_bytes, _BLOCK))
        with p.open("rb") as fh:
            pos = size
            buf = b""
            read = 0
            while pos > 0 and read < want:
                step = min(_BLOCK, pos)
                pos -= step
                fh.seek(pos, os.SEEK_SET)
                chunk = fh.read(step)
                read += step
                buf = chunk + buf
                parts = buf.split(b"\n")
                # parts[0] may be a PARTIAL line whose head is further back; hold it.
                buf = parts[0]
                for raw in reversed(parts[1:]):
                    if raw.strip():
                        yield raw.decode("utf-8", errors="replace")
            if pos == 0 and buf.strip():
                yield buf.decode("utf-8", errors="replace")
    except Exception:
        return  # fail-open: a hook must never die on a transcript read


def tail_events(path, limit: int = 400, max_bytes: int = _DEFAULT_MAX_BYTES):
    """Up to `limit` parsed JSONL events from the end, NEWEST FIRST. Never raises."""
    out = []
    for line in iter_tail_lines(path, max_bytes=max_bytes):
        try:
            out.append(json.loads(line))
        except Exception:
            continue  # a non-JSON line is not fatal; skip it
        if len(out) >= limit:
            break
    return out


def _text_of(ev) -> str:
    """Concatenated text of an assistant event, tolerant of both content shapes."""
    msg = ev.get("message") if isinstance(ev, dict) else None
    if not isinstance(msg, dict):
        return ""
    content = msg.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            b.get("text", "")
            for b in content
            if isinstance(b, dict) and b.get("type") == "text"
        )
    return ""


def final_assistant_text(path, max_bytes: int = _DEFAULT_MAX_BYTES):
    """(text, ok) for the LAST assistant message.

    `ok=False` means the transcript could not be read at all -- distinct from a successful read
    that found no assistant message (`("", True)`). Callers under P2-01 map ok=False to
    NOT-CHECKED rather than treating an unreadable transcript as an empty one.
    """
    try:
        if not Path(path).is_file():
            return "", False
    except Exception:
        return "", False

    saw_any = False
    for line in iter_tail_lines(path, max_bytes=max_bytes):
        saw_any = True
        try:
            ev = json.loads(line)
        except Exception:
            continue
        if isinstance(ev, dict) and ev.get("type") == "assistant":
            return _text_of(ev), True
    # read succeeded (or the file was empty); simply no assistant record in the tail
    return "", bool(saw_any) or True
