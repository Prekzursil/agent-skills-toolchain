"""Tests for ``monitorcore.cockpit`` — the interactive drill driver + the --once export
lane (WU5 degradation, WU6 marks integration, WU8 --once/push), 100% line+branch.

The interactive loop and the CLI are driven entirely through injected seams (a fake source,
a scripted ``read_key``, a recording ``write``/``out``/``runner``/``interactive``), so no
real terminal, keypress, toast, or clock is touched.
"""

from __future__ import annotations

import pytest

from monitorcore.cockpit import (
    _blocked,
    _mtime,
    interactive_supported,
    main,
    notify,
    once_frame,
    push_text,
    run_interactive,
    stall_marks,
)
from monitorcore.codex_source import CodexPayload
from monitorcore.codex_tail import CodexThread, ToolEvent
from monitorcore.contract import Snapshot, SourceState
from monitorcore.nav import ViewState
from monitorcore.stall import StallTracker

NOW = 1_784_283_000.0


def _th(
    key: str,
    *,
    label: str = "",
    status: str = "idle",
    aborted: bool = False,
    path: str = "p",
    last_ev_status: str | None = None,
) -> CodexThread:
    th = CodexThread(key=key, source="stream", path=path, label=label)
    th.status = status
    th.aborted = aborted
    th.last_ts = NOW
    if last_ev_status is not None:
        th.add_event(ToolEvent("cmd", "shell", "x", last_ev_status, None, NOW))
    return th


def _snap(*threads: CodexThread, ts: float = NOW) -> Snapshot[CodexPayload]:
    return Snapshot(
        source_id="codexmon",
        ts=ts,
        reachable=True,
        stale=False,
        state=SourceState.IDLE,
        headline="codex [idle] 0 running / 0 done / 0 aborted of 0",
        payload=CodexPayload(threads=tuple(threads)),
        age_s=None,
        error=None,
    )


class _FakeSource:
    def __init__(self, snap: Snapshot[CodexPayload]) -> None:
        self._snap = snap
        self.polls = 0

    def poll(self) -> Snapshot[CodexPayload]:
        self.polls += 1
        return self._snap


# ───────────────────────────── interactive_supported ─────────────────────────────
@pytest.mark.parametrize(
    ("is_tty", "wt", "term", "ok"),
    [
        (True, None, None, True),  # plain console → interactive
        (False, None, None, False),  # not a tty → degrade
        (True, "abc123", None, False),  # Windows Terminal / ConPTY → degrade
        (True, None, "vscode", False),  # VS Code integrated terminal → degrade
    ],
)
def test_interactive_supported(is_tty, wt, term, ok) -> None:
    assert interactive_supported(is_tty=is_tty, wt_session=wt, term_program=term) is ok


# ───────────────────────────── _mtime ─────────────────────────────
def test_mtime_reads_a_real_file(tmp_path) -> None:
    f = tmp_path / "s.jsonl"
    f.write_text("{}", encoding="utf-8")
    assert isinstance(_mtime(str(f)), float)


def test_mtime_returns_none_for_a_missing_file(tmp_path) -> None:
    assert _mtime(str(tmp_path / "gone.jsonl")) is None


# ───────────────────────────── _blocked ─────────────────────────────
def test_blocked_only_for_an_idle_thread_with_an_inflight_event() -> None:
    assert _blocked(_th("a", status="running", last_ev_status="running")) is False
    assert _blocked(_th("b", status="idle")) is False  # idle but no events
    assert (
        _blocked(_th("c", status="idle", last_ev_status="ok")) is False
    )  # not inflight
    assert _blocked(_th("d", status="idle", last_ev_status="running")) is True


# ───────────────────────────── stall_marks (WU6) ─────────────────────────────
def test_stall_marks_corroborated_stall_needs_two_polls() -> None:
    tr = StallTracker()
    th = _th("a", status="idle")
    stale = lambda _p: None  # noqa: E731 - mtime unreadable ⇒ mtime_stale signal
    first = stall_marks(tr, [th], NOW, stale_s=90.0, mtime_fn=stale)
    assert "a" not in first  # frozen=1 → single signal, no stall yet
    second = stall_marks(tr, [th], NOW, stale_s=90.0, mtime_fn=stale)
    assert second["a"] == "STALL"  # frozen=2 AND mtime stale → corroborated


def test_stall_marks_stale_by_age_path() -> None:
    tr = StallTracker()
    th = _th("a", status="idle")
    old = lambda _p: NOW - 1000.0  # noqa: E731 - mtime present but far past the window
    stall_marks(tr, [th], NOW, stale_s=90.0, mtime_fn=old)
    second = stall_marks(tr, [th], NOW, stale_s=90.0, mtime_fn=old)
    assert second["a"] == "STALL"


def test_stall_marks_flags_blocked_when_mtime_is_fresh() -> None:
    tr = StallTracker()
    th = _th("a", status="idle", last_ev_status="running")
    fresh = lambda _p: NOW  # noqa: E731 - mtime current ⇒ not stale
    marks = stall_marks(tr, [th], NOW, stale_s=90.0, mtime_fn=fresh)
    assert marks["a"] == "BLOCKED"


def test_stall_marks_no_mark_for_a_healthy_active_thread() -> None:
    tr = StallTracker()
    th = _th("a", status="running")
    fresh = lambda _p: NOW  # noqa: E731
    assert stall_marks(tr, [th], NOW, stale_s=90.0, mtime_fn=fresh) == {}


# ───────────────────────────── push_text / notify ─────────────────────────────
def test_push_text_carries_the_headline() -> None:
    text = push_text(_snap())
    assert text.startswith("[codexmon] ")
    assert "idle" in text


def test_notify_invokes_the_runner_with_the_text_in_env() -> None:
    calls: list[dict] = []

    def runner(argv, **kw):
        calls.append({"argv": argv, "kw": kw})
        return None

    notify("hello", runner=runner)
    assert calls and calls[0]["kw"]["env"]["MC_PUSH"] == "hello"


def test_notify_swallows_a_runner_failure() -> None:
    def boom(argv, **kw):
        raise OSError("no powershell")

    notify("hi", runner=boom)  # must not raise


# ───────────────────────────── once_frame ─────────────────────────────
def test_once_frame_is_read_only() -> None:
    rows = once_frame(_snap(_th("t1", label="audit", status="running")), 120)
    assert rows[0].startswith("  CODEX COCKPIT")
    assert not any(r.startswith("> ") for r in rows)  # no cursor in --once


# ───────────────────────────── run_interactive ─────────────────────────────
def test_run_interactive_renders_until_quit() -> None:
    src = _FakeSource(_snap(_th("t1", label="audit", status="running")))
    keys = iter(["down", "q"])
    frames: list[list[str]] = []
    final = run_interactive(
        src,
        read_key=lambda: next(keys),
        write=frames.append,
        clock=lambda: NOW,
        cols_fn=lambda: 120,
    )
    assert final.quit is True
    assert len(frames) == 2  # rendered before each keypress
    assert src.polls == 2


def test_run_interactive_accepts_injected_initial_and_tracker() -> None:
    src = _FakeSource(_snap(_th("t1", label="audit")))
    frames: list[list[str]] = []
    final = run_interactive(
        src,
        read_key=lambda: "q",
        write=frames.append,
        clock=lambda: NOW,
        initial=ViewState(selected=0),
        tracker=StallTracker(),
        mtime_fn=lambda _p: NOW,
    )
    assert final.quit is True
    assert len(frames) == 1


# ───────────────────────────── main ─────────────────────────────
def test_main_once_prints_a_frame() -> None:
    out: list[str] = []
    rc = main(
        ["--once", "--width", "120"],
        source=_FakeSource(_snap(_th("t1", label="audit", status="running"))),
        out=out.append,
        clock=lambda: NOW,
    )
    assert rc == 0
    assert out[0].startswith("  CODEX COCKPIT")


def test_main_once_fires_a_push_when_requested() -> None:
    pushed: list[str] = []
    main(
        ["--once", "--notify"],
        source=_FakeSource(_snap()),
        out=lambda _s: None,
        clock=lambda: NOW,
        notify_fn=pushed.append,
    )
    assert pushed and pushed[0].startswith("[codexmon] ")


def test_main_degrades_to_once_under_an_unsupported_terminal() -> None:
    out: list[str] = []
    called = {"interactive": False}

    def _interactive(*a, **k):
        called["interactive"] = True
        return ViewState()

    rc = main(
        [],  # no --once, but the terminal is unsupported
        source=_FakeSource(_snap(_th("t1", label="audit"))),
        out=out.append,
        clock=lambda: NOW,
        interactive=_interactive,
        supported_fn=lambda: False,
    )
    assert rc == 0
    assert out  # the read-only frame was rendered
    assert called["interactive"] is False  # the drill loop never started


def test_main_drills_when_the_terminal_is_supported() -> None:
    seen: dict = {}

    def _interactive(src, **kw):
        seen["src"] = src
        seen["cols"] = kw["cols_fn"]()
        return ViewState()

    src = _FakeSource(_snap())
    rc = main(
        ["--width", "88"],
        source=src,
        clock=lambda: NOW,
        interactive=_interactive,
        supported_fn=lambda: True,
    )
    assert rc == 0
    assert seen["src"] is src
    assert seen["cols"] == 88


def test_main_builds_a_default_source_when_none_given(tmp_path) -> None:
    out: list[str] = []
    rc = main(
        [
            "--once",
            "--stream-dir",
            str(tmp_path / "s"),
            "--sessions-dir",
            str(tmp_path / "r"),
        ],
        source=None,  # force the real CodexSource construction path
        out=out.append,
        clock=lambda: NOW,
    )
    assert rc == 0
    assert out[0].startswith("  CODEX COCKPIT")  # empty fleet → title only
