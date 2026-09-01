"""Discover local mirrors of remote worker event streams.

The unified cockpit's databricks/workers pane is a LOCAL file adapter — it never
opens a socket. Scaleway, Databricks, Modal, RunPod, or a laptop all look the same
once their NDJSON has been mirrored under ``~/.claude/remote-workers/<name>/``.

This module does NO network I/O. A separate puller (``remote_pull.py``) is what
copies bytes onto this disk. ``poll`` remaining raise-free is the adapter's job.
"""

from __future__ import annotations

import os
from pathlib import Path

__all__ = [
    "EVENTS_NAME",
    "WORKERS_DIRNAME",
    "discover_event_streams",
    "preferred_remote_events_path",
    "resolve_events_path",
    "workers_root",
]

WORKERS_DIRNAME = "remote-workers"
EVENTS_NAME = "events.ndjson"


def workers_root(home: str | None = None) -> Path:
    """``~/.claude/remote-workers`` — one subdirectory per worker name."""
    base = Path(home) if home else Path.home()
    return base / ".claude" / WORKERS_DIRNAME


def discover_event_streams(home: str | None = None) -> tuple[Path, ...]:
    """Existing ``events.ndjson`` files, newest mtime first. Missing root → ()."""
    root = workers_root(home)
    if not root.is_dir():
        return ()
    found: list[Path] = []
    for child in root.iterdir():
        if not child.is_dir():
            continue
        events = child / EVENTS_NAME
        if events.is_file():
            found.append(events)
    found.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return tuple(found)


def preferred_remote_events_path(home: str | None = None) -> str | None:
    """The stream the cockpit should open, or None if nothing has been mirrored.

    Precedence: ``current/events.ndjson`` if that file exists, else the newest
    sibling. Absence is None — never a fabricated path that would flip the pane
    from UNMEASURED to "0 units observed".
    """
    root = workers_root(home)
    pinned = root / "current" / EVENTS_NAME
    if pinned.is_file():
        return str(pinned)
    found = discover_event_streams(home)
    if found:
        return str(found[0])
    return None


def resolve_events_path() -> str:
    """Env override, then a mirrored remote worker, then the historical dbx default."""
    env = os.environ.get("DBX_MONITOR_EVENTS") or os.environ.get(
        "MONITORCORE_EVENTS_PATH"
    )
    if env:
        return env
    remote = preferred_remote_events_path()
    if remote:
        return remote
    return os.path.join(os.path.expanduser("~"), ".dbxmon", "events.jsonl")
