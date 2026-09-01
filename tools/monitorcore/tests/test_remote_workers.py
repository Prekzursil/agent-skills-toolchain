"""Local-only discovery of mirrored remote-worker event streams."""

from __future__ import annotations

from pathlib import Path

from monitorcore.databricks_source import default_events_path
from monitorcore.remote_workers import (
    discover_event_streams,
    preferred_remote_events_path,
    resolve_events_path,
    workers_root,
)


def test_missing_root_is_empty_not_a_fabricated_path(tmp_path: Path) -> None:
    home = str(tmp_path / "no-such")
    assert workers_root(home).name == "remote-workers"
    assert discover_event_streams(home) == ()
    assert preferred_remote_events_path(home) is None


def test_current_pin_beats_newer_sibling(tmp_path: Path) -> None:
    root = tmp_path / ".claude" / "remote-workers"
    old = root / "scaleway-p2"
    new = root / "other"
    pin = root / "current"
    for d in (old, new, pin):
        d.mkdir(parents=True)
    (old / "events.ndjson").write_text("{}\n", encoding="utf-8")
    newer = new / "events.ndjson"
    newer.write_text("{}\n", encoding="utf-8")
    pinned = pin / "events.ndjson"
    pinned.write_text("{}\n", encoding="utf-8")
    # make "other" newer on disk
    newer.write_text('{"x":1}\n', encoding="utf-8")
    assert preferred_remote_events_path(str(tmp_path)) == str(pinned)


def test_newest_sibling_when_no_current(tmp_path: Path) -> None:
    root = tmp_path / ".claude" / "remote-workers"
    a = root / "a"
    b = root / "b"
    a.mkdir(parents=True)
    b.mkdir(parents=True)
    (a / "events.ndjson").write_text("a\n", encoding="utf-8")
    (b / "events.ndjson").write_text("b\n", encoding="utf-8")
    # a stray FILE in the root is skipped (workers are directories) ...
    (root / "README.txt").write_text("not a worker\n", encoding="utf-8")
    # ... and a worker dir with no stream yet contributes nothing rather than raising
    (root / "no-stream-yet").mkdir()
    found = discover_event_streams(str(tmp_path))
    assert len(found) == 2
    pick = preferred_remote_events_path(str(tmp_path))
    assert pick is not None
    assert Path(pick).name == "events.ndjson"


def test_resolve_honours_dbx_env(monkeypatch, tmp_path: Path) -> None:
    # Hermetic home: a REAL mirrored stream under this box's ~/.claude/remote-workers
    # (current/events.ndjson exists here) would otherwise win the no-env fallback
    # assertions below — measured 2026-08-18: exactly that made this test
    # box-state-dependent (green on a fresh CI runner, red on the authoring box).
    monkeypatch.setenv("USERPROFILE", str(tmp_path))  # Windows expanduser / Path.home
    monkeypatch.setenv("HOME", str(tmp_path))  # POSIX expanduser / Path.home
    monkeypatch.setenv("DBX_MONITOR_EVENTS", "/srv/dbx/events.jsonl")
    assert resolve_events_path() == "/srv/dbx/events.jsonl"
    assert default_events_path() == "/srv/dbx/events.jsonl"
    monkeypatch.delenv("DBX_MONITOR_EVENTS", raising=False)
    monkeypatch.setenv("MONITORCORE_EVENTS_PATH", str(tmp_path / "w.ndjson"))
    assert default_events_path().endswith("w.ndjson")
    monkeypatch.delenv("MONITORCORE_EVENTS_PATH", raising=False)
    # The isolated home holds no mirror -> the historical dbx default, deterministically.
    fallback = default_events_path()
    assert fallback.endswith("events.jsonl")
    assert ".dbxmon" in fallback
    # Once a mirror IS pinned under the (isolated) home, it beats that fallback.
    pin = tmp_path / ".claude" / "remote-workers" / "current"
    pin.mkdir(parents=True)
    stream = pin / "events.ndjson"
    stream.write_text("{}\n", encoding="utf-8")
    assert resolve_events_path() == str(stream)
