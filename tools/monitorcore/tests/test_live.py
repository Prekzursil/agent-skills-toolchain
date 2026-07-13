"""The shared poll/render loop used by every launchable ``MonitorSource`` adapter."""

from __future__ import annotations

import io
from dataclasses import dataclass

from monitorcore.contract import Snapshot, SourceState
from monitorcore.live import run


@dataclass
class FakeSource:
    id: str = "fake"
    polls: int = 0

    def poll(self):
        self.polls += 1
        return Snapshot(
            source_id=self.id,
            ts=float(self.polls),
            reachable=True,
            stale=False,
            state=SourceState.RUNNING,
            headline=f"poll {self.polls}",
            payload=self.polls,
        )

    def render_native(self, snap):
        return f"native {snap.payload}"


def test_run_once_polls_and_renders_without_terminal_clear():
    source = FakeSource()
    out = io.StringIO()

    assert run(source, once=True, out=out, sleeper=lambda _seconds: None) == 0

    assert source.polls == 1
    assert out.getvalue() == "native 1\n"


def test_run_live_clears_each_frame_and_stops_cleanly_on_keyboard_interrupt():
    source = FakeSource()
    out = io.StringIO()

    def _interrupt(_seconds):
        raise KeyboardInterrupt

    assert run(source, interval=0.25, out=out, sleeper=_interrupt) == 0

    assert source.polls == 1
    assert out.getvalue().startswith("\x1b[2J\x1b[Hnative 1\n")


def test_run_uses_stdout_when_output_not_injected(monkeypatch):
    source = FakeSource()
    out = io.StringIO()
    monkeypatch.setattr("sys.stdout", out)

    assert run(source, once=True, sleeper=lambda _seconds: None) == 0
    assert out.getvalue() == "native 1\n"
