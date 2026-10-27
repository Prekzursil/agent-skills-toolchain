"""Tests for ``monitorcore.event_feed`` — the pure ASCII event-feed renderer over a
thread's ``deque[ToolEvent]`` (WU2), 100% line+branch.
"""

from __future__ import annotations

from collections import deque

import pytest

from monitorcore.codex_tail import CodexThread, ToolEvent
from monitorcore.event_feed import (
    event_glyph,
    event_row,
    event_rows,
    kind_glyph,
    status_glyph,
    thread_rows,
)

# A fixed epoch → deterministic UTC HH:MM:SS ("2021-01-01 00:00:00Z" = 1609459200).
_TS = 1609459200.0  # 00:00:00 UTC
_TS2 = 1609459323.0  # 00:02:03 UTC


def _ev(
    kind: str = "cmd",
    label: str = "command",
    detail: str = "pytest -q",
    status: str = "ok",
    dur: float | None = None,
    ts: float = _TS,
) -> ToolEvent:
    return ToolEvent(
        kind=kind, label=label, detail=detail, status=status, dur=dur, ts=ts
    )


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        ("cmd", "$"),
        ("tool", "*"),
        ("patch", "+"),
        ("msg", ">"),
        ("think", "~"),
        ("weird", "?"),  # unknown kind → fallback glyph
    ],
)
def test_kind_glyph(kind: str, expected: str) -> None:
    assert kind_glyph(kind) == expected


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("running", "."),
        ("ok", "o"),
        ("error", "x"),
        ("", " "),  # no status → blank
        ("weird", "?"),  # unknown status → fallback glyph
    ],
)
def test_status_glyph(status: str, expected: str) -> None:
    assert status_glyph(status) == expected


def test_event_glyph_is_kind_then_status() -> None:
    assert event_glyph(_ev(kind="tool", status="error")) == "*x"
    assert event_glyph(_ev(kind="msg", status="")) == "> "


def test_event_row_full_with_label_detail_and_dur() -> None:
    row = event_row(
        _ev(kind="tool", label="shell", detail="pytest -q", status="ok", dur=3.0), 80
    )
    assert row == "00:00:00 *o shell: pytest -q (00:03)"


def test_event_row_detail_only_uses_detail_as_text() -> None:
    row = event_row(_ev(kind="patch", label="", detail="catalogue.py", status="ok"), 80)
    assert row == "00:00:00 +o catalogue.py"


def test_event_row_no_label_no_detail_is_glyph_only() -> None:
    row = event_row(_ev(kind="think", label="", detail="", status=""), 80)
    assert row == "00:00:00 ~"


def test_event_row_zero_ts_shows_placeholder_time() -> None:
    row = event_row(
        _ev(kind="cmd", label="command", detail="", status="running", ts=0.0), 80
    )
    assert row == "--:--:-- $. command"


def test_event_row_clips_long_detail_with_ellipsis() -> None:
    long = "x" * 200
    row = event_row(_ev(kind="cmd", label="command", detail=long, status="ok"), 20)
    assert len(row) == 20
    assert row.endswith("…")


def test_event_row_uses_deterministic_utc_time() -> None:
    row = event_row(_ev(kind="msg", label="message", detail="", status="", ts=_TS2), 80)
    assert row.startswith("00:02:03 ")


def test_event_rows_all_when_no_limit() -> None:
    events = deque(_ev(detail=f"cmd{i}") for i in range(3))
    rows = event_rows(events, 80)
    assert len(rows) == 3
    assert rows[0] == "00:00:00 $o command: cmd0"


def test_event_rows_limit_keeps_most_recent_tail() -> None:
    events = deque(_ev(detail=f"cmd{i}") for i in range(5))
    rows = event_rows(events, 80, limit=2)
    assert [r.split(": ")[-1] for r in rows] == ["cmd3", "cmd4"]


def test_event_rows_limit_zero_is_empty() -> None:
    events = deque(_ev() for _ in range(3))
    assert event_rows(events, 80, limit=0) == []


def test_event_rows_negative_limit_is_empty() -> None:
    events = deque(_ev() for _ in range(3))
    assert event_rows(events, 80, limit=-4) == []


def test_event_rows_applies_indent() -> None:
    events = deque([_ev(kind="cmd", label="command", detail="go", status="ok")])
    rows = event_rows(events, 80, indent="  ")
    assert rows == ["  00:00:00 $o command: go"]


def test_event_rows_indent_wider_than_width_still_returns_a_row() -> None:
    events = deque([_ev()])
    rows = event_rows(
        events, 3, indent="      "
    )  # inner width clamps to 0 → empty body
    assert rows == ["      "]


def _thread_with_events(*events: ToolEvent) -> CodexThread:
    th = CodexThread(
        key="stream:x.jsonl", source="stream", path="x.jsonl", label="fix-shim"
    )
    th.start_ts = _TS
    th.last_ts = _TS
    th.status = "running"
    for ev in events:
        th.add_event(ev)
    return th


def test_thread_rows_without_events_is_one_indented_board_line() -> None:
    th = _thread_with_events(_ev())
    rows = thread_rows(th, _TS, 120)
    assert len(rows) == 1
    assert rows[0].startswith("    ")  # 4-space thread indent
    assert "fix-shim" in rows[0]


def test_thread_rows_with_events_interleaves_the_feed() -> None:
    th = _thread_with_events(
        _ev(kind="tool", label="shell", detail="pytest -q", status="error"),
        _ev(kind="patch", label="patch", detail="catalogue.py", status="ok"),
    )
    rows = thread_rows(th, _TS, 120, show_events=True)
    assert len(rows) == 3  # board line + two event rows
    assert rows[1].startswith("      ")  # 6-space event indent under the thread
    assert "shell: pytest -q" in rows[1]
    assert "catalogue.py" in rows[2]


def test_thread_rows_event_limit_is_honoured() -> None:
    th = _thread_with_events(*[_ev(detail=f"c{i}") for i in range(6)])
    rows = thread_rows(th, _TS, 120, show_events=True, event_limit=2)
    assert len(rows) == 3  # board line + last two events
    assert rows[-1].endswith("c5")


def test_thread_rows_narrow_width_clips_board_line_to_indent() -> None:
    th = _thread_with_events(_ev())
    rows = thread_rows(th, _TS, 5)  # inner width < 1 → blank board body after indent
    assert rows == ["    "]
