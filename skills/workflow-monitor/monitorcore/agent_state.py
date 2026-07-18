"""Transcript→coarse-state derivation (Fork C) + the unified agent state bucket.

Two pure, stdlib-only pieces the agent domain needs:

* :func:`bucket_agent` — the SINGLE source of truth for the coarse
  ``running`` / ``done`` / ``error`` / ``idle`` bucket that wfmon previously duplicated as
  ``model._state_bucket`` **and** ``workflow_monitor._bucket`` (identical logic in two
  places). Both now delegate here, killing the duplication. It maps a manifest agent row
  (its ``errored`` / ``state`` / ``running`` flags, plus an optional journal state) onto the
  bucket; ``journal_state=None`` reproduces the former ``_bucket`` exactly.

* :func:`agent_status` — the transcript-driven deriver ported from the retired agent-monitor
  Tkinter UI. Unlike a single mtime cutoff (which mislabels a long-thinking or a
  just-finished agent), it reads the tail of the transcript to distinguish
  ``running`` (fresh) / ``working`` (recently active or awaiting a long tool call) /
  ``done`` (last event is an assistant text turn) / ``stalled`` (silent past its dead-man
  window). ``stalled`` is the freeze/dead-man signal the watchdog and the PR-G alert rail
  are built around, so it is preserved verbatim.

Both are read-only and fully deterministic under an injected clock (``now``), so they reach
100% branch coverage on any platform.
"""

from __future__ import annotations

import json
import os
import time

__all__ = ["FRESH", "STALL", "agent_status", "bucket_agent"]

FRESH = 45.0  # mtime age (s) under which an agent is definitely RUNNING
STALL = 600.0  # silence (s) after which a non-finished agent is STALLED


def bucket_agent(
    *,
    errored: bool,
    state: str | None,
    running: bool,
    journal_state: str | None = None,
) -> str:
    """Collapse a manifest agent row into a coarse display bucket.

    ``error`` if the manifest marks the agent errored; else ``done`` if the journal recorded
    a ``result`` OR the manifest state is ``done``; else ``running`` if the agent is in a
    running state; else ``idle``. Passing ``journal_state=None`` reproduces the former
    ``workflow_monitor._bucket``; passing the journal state reproduces ``model._state_bucket``.
    """
    if errored:
        return "error"
    if journal_state == "result" or state == "done":
        return "done"
    if running:
        return "running"
    return "idle"


def _last_entry_shape(path: str) -> tuple[str | None, str | None]:
    """``(last_block_type, role)`` of the last content-bearing event — a cheap tail read."""
    try:
        sz = os.path.getsize(path)
        with open(path, "rb") as fh:
            fh.seek(max(0, sz - 40_000))
            data = fh.read().decode("utf-8", "ignore")
    except OSError:
        return (None, None)
    for line in reversed(data.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        msg = obj.get("message") if isinstance(obj.get("message"), dict) else {}
        content = msg.get("content")
        blocks = (
            content
            if isinstance(content, list)
            else ([{"type": "text"}] if isinstance(content, str) else [])
        )
        for b in reversed(blocks):
            if isinstance(b, dict) and b.get("type"):
                return (b.get("type"), msg.get("role"))
    return (None, None)


# path -> (mtime, terminal_status); avoids re-reading finished agents whose mtime is frozen.
_STATUS_CACHE: dict[str, tuple[float, str]] = {}


def agent_status(
    path: str,
    *,
    now: float | None = None,
    fresh: float = FRESH,
    stall: float = STALL,
) -> tuple[str, float]:
    """Return ``(state, age_s)`` for one transcript: ``running`` | ``working`` | ``done`` | ``stalled``.

    A missing/unreadable transcript is treated as ``stalled``. A transcript touched within
    ``fresh`` seconds is ``running``. Otherwise the tail is inspected: a trailing assistant
    ``text`` turn is ``done``; silence past ``stall`` seconds is ``stalled``; anything else is
    ``working``. Terminal states (``done`` / ``stalled``) are cached by frozen mtime so a
    finished agent is not re-read. ``now`` is injectable for deterministic tests.
    """
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return ("stalled", 1e9)
    clock = time.time() if now is None else now
    age = clock - mtime
    if age < fresh:
        return ("running", age)
    cached = _STATUS_CACHE.get(path)
    if cached and cached[0] == mtime:
        return (cached[1], age)
    last_type, role = _last_entry_shape(path)
    if last_type == "text" and role == "assistant":
        status = "done"
    elif age > stall:
        status = "stalled"
    else:
        status = "working"
    if status in ("done", "stalled"):
        _STATUS_CACHE[path] = (mtime, status)
    return (status, age)
