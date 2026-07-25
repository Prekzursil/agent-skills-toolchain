"""Tests for ``monitorcore.codex_source`` — the CodexSource adapter, 100% line+branch.

Proves the contract's cardinal rules on the first in-package adapter:

* **poll never throws** — an injected poller that raises ``Exception`` yields a stale /
  unreachable :class:`Snapshot` with the (redacted) error text and NO propagation, and
  RETAINS the last-good payload; a ``BaseException`` (Ctrl-C) is deliberately not
  swallowed.
* **typed payload** — :class:`CodexPayload` carries the native ``CodexThread`` tuple,
  never a flattened dict, and ``isinstance(CodexSource(...), MonitorSource)`` holds.
* every reachable / unreachable / error / running / done / idle branch, the headline,
  ``render_native``, the ``ReportDoc`` mapping (rendered through the shared Markdown
  renderer as a smoke check), and the signature-only ``alert`` classifier.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from monitorcore import codex_tail as ct
from monitorcore.codex_source import CodexPayload, CodexSource
from monitorcore.contract import MonitorSource, Snapshot, SourceState
from monitorcore.render_md import render_md

_FIXTURES = Path(__file__).parent / "fixtures"
_STREAM_FIXTURE = _FIXTURES / "codex-stream-wave0.jsonl"

NOW = 1_784_283_000.0
SK_TOKEN = "sk-" + "b" * 20  # programmatic, never a literal secret shape


def _poller(tmp_path, **kw) -> ct.Poller:
    stream = tmp_path / "streams"
    sessions = tmp_path / "sessions"
    stream.mkdir(parents=True, exist_ok=True)
    sessions.mkdir(parents=True, exist_ok=True)
    kw.setdefault("clock", lambda: NOW)
    return ct.Poller(str(stream), str(sessions), **kw)


def _seeded_source(tmp_path, *threads: ct.CodexThread, **kw) -> CodexSource:
    """A source over empty real dirs whose poller is pre-seeded with crafted threads."""
    poller = _poller(tmp_path)
    for th in threads:
        poller.threads[th.key] = th
        poller.tails[th.key] = ct.Tail(th.path)
    kw.setdefault("clock", lambda: NOW)
    return CodexSource(poller=poller, **kw)


def _thread(**kw) -> ct.CodexThread:
    base = {"key": "k", "source": "stream", "path": "p"}
    base.update(kw)
    return ct.CodexThread(**base)


class _BoomPoller(ct.Poller):
    def discover(self) -> None:
        raise RuntimeError(f"stream dir gone {SK_TOKEN}")


class _CtrlCPoller(ct.Poller):
    def discover(self) -> None:
        raise KeyboardInterrupt


# ───────────────────────── contract shape ─────────────────────────
def test_source_satisfies_runtime_checkable_protocol(tmp_path):
    src = _seeded_source(tmp_path)
    assert isinstance(src, MonitorSource)
    assert src.id == "codexmon"


def test_default_poller_uses_env_dirs(tmp_path, monkeypatch):
    monkeypatch.setenv("CODEX_STREAM_DIR", str(tmp_path / "s"))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex"))
    src = CodexSource(clock=lambda: NOW)
    snap = src.poll()  # missing dirs are quietly empty, never an error
    assert snap.reachable is True
    assert snap.state is SourceState.IDLE
    assert snap.payload == CodexPayload()


def test_explicit_dirs_build_the_poller(tmp_path):
    src = CodexSource(
        stream_dir=str(tmp_path / "s"),
        sessions_dir=str(tmp_path / "r"),
        since_min=5.0,
        max_threads=3,
        clock=lambda: NOW,
    )
    assert src._poller.since_min == 5.0
    assert src._poller.max_threads == 3


# ───────────────────────── poll: reachable paths ─────────────────────────
def test_poll_over_stream_fixture_reaches_running(tmp_path):
    poller = _poller(tmp_path)
    shutil.copy(_STREAM_FIXTURE, poller.stream_dir / _STREAM_FIXTURE.name)
    src = CodexSource(poller=poller, clock=lambda: NOW)
    snap = src.poll()
    assert snap.reachable and not snap.stale
    # the fixture thread completed <3s before NOW (stream last_ts == clock) → running
    assert snap.state is SourceState.RUNNING
    (th,) = snap.payload.threads
    assert isinstance(th, ct.CodexThread)
    assert snap.headline == "codex [running] 1 running / 0 done / 0 aborted of 1"
    assert snap.age_s == 0.0  # newest activity == the poll epoch (stream arrival)


def test_poll_age_is_none_when_no_thread_ever_active(tmp_path):
    src = _seeded_source(tmp_path, _thread(last_ts=0.0))
    snap = src.poll()
    assert snap.age_s is None
    assert snap.state is SourceState.IDLE  # quiet thread → idle


def test_poll_age_measures_newest_thread(tmp_path):
    src = _seeded_source(
        tmp_path,
        _thread(key="a", last_ts=NOW - 50),
        _thread(key="b", last_ts=NOW - 5),
    )
    snap = src.poll()
    assert snap.age_s == 5.0
    assert snap.state is SourceState.RUNNING


# ───────────────────────── poll: never throws ─────────────────────────
def test_poll_failure_without_history_returns_empty_payload(tmp_path):
    src = CodexSource(
        poller=_BoomPoller(str(tmp_path / "s"), str(tmp_path / "r")),
        clock=lambda: NOW,
    )
    snap = src.poll()
    assert snap.reachable is False and snap.stale is True
    assert snap.state is SourceState.UNREACHABLE
    assert snap.payload == CodexPayload()
    assert snap.error is not None and SK_TOKEN in snap.error  # raw error kept for logs
    assert snap.headline == "unreachable: stream dir gone [REDACTED:api-key]"


def test_poll_failure_retains_last_good_payload(tmp_path):
    poller = _poller(tmp_path)
    shutil.copy(_STREAM_FIXTURE, poller.stream_dir / _STREAM_FIXTURE.name)
    src = CodexSource(poller=poller, clock=lambda: NOW)
    good = src.poll()
    assert good.reachable

    def boom() -> None:
        raise RuntimeError("tick failed")

    poller.discover = boom  # type: ignore[method-assign]
    bad = src.poll()
    assert bad.reachable is False
    assert bad.payload is good.payload  # last-good retained, not rebuilt


def test_poll_lets_base_exception_propagate(tmp_path):
    src = CodexSource(
        poller=_CtrlCPoller(str(tmp_path / "s"), str(tmp_path / "r")),
        clock=lambda: NOW,
    )
    with pytest.raises(KeyboardInterrupt):
        src.poll()


# ───────────────────────── coarse-state derivation ─────────────────────────
def test_derive_state_matrix():
    derive = CodexSource._derive_state
    assert derive(()) is SourceState.IDLE
    assert (
        derive((_thread(status="aborted"), _thread(status="running")))
        is SourceState.ERROR
    )
    assert (
        derive((_thread(status="running"), _thread(status="done")))
        is SourceState.RUNNING
    )
    assert derive((_thread(status="done"), _thread(status="done"))) is SourceState.DONE
    assert derive((_thread(status="done"), _thread(status="idle"))) is SourceState.IDLE


def test_poll_state_error_on_aborted_thread(tmp_path):
    src = _seeded_source(tmp_path, _thread(aborted=True, last_ts=NOW))
    snap = src.poll()
    assert snap.state is SourceState.ERROR
    assert snap.headline.endswith("1 aborted of 1")


def test_poll_state_done_when_all_completed(tmp_path):
    src = _seeded_source(tmp_path, _thread(completed=True, last_ts=NOW - 30))
    snap = src.poll()
    assert snap.state is SourceState.DONE


# ───────────────────────── contract surface ─────────────────────────
def test_render_native_headline_fallback_and_board(tmp_path):
    src = _seeded_source(tmp_path)
    empty = src.poll()
    assert src.render_native(empty) == empty.headline
    src2 = _seeded_source(
        tmp_path,
        _thread(key="a", label="A", last_ts=NOW - 1),
        _thread(key="b", label="B"),
    )
    snap = src2.poll()
    native = src2.render_native(snap)
    assert isinstance(native, str)
    assert native.count("\n") == 1  # one board line per thread
    assert "A" in native and "B" in native


def test_export_model_empty_and_populated(tmp_path):
    src = _seeded_source(tmp_path)
    doc = src.export_model(src.poll())
    assert doc.title == "codexmon"
    assert doc.blocks == ()
    assert doc.active is False
    assert doc.generated_at == "2026-07-17T10:10:00+00:00"  # derived from poll epoch
    assert dict(doc.rollup) == {
        "total": 0,
        "done": 0,
        "error": 0,
        "running": 0,
        "idle": 0,
        "tokens": 0,
    }

    busy = _seeded_source(
        tmp_path,
        _thread(
            key="a",
            label="wave0",
            model="gpt-5.6-sol",
            prompt="fix tests",
            tokens_total=1200,
            tool_count=3,
            turns=2,
            last_ts=NOW - 1,
        ),
    )
    snap = busy.poll()
    doc = busy.export_model(snap)
    assert doc.active is True
    (card,) = doc.blocks
    assert card.card is True
    assert (card.title, card.badge, card.model) == ("wave0", "running", "gpt-5.6-sol")
    assert (card.tokens, card.tool_calls, card.task) == (1200, 3, "fix tests")
    assert card.lead == "2 turns · stream"
    md = render_md(doc)  # smoke: the shared renderer consumes the mapping
    assert "wave0" in md


def test_export_model_populates_section_timeline_from_events(tmp_path):
    """WU8: export_model maps the thread's ToolEvent deque onto Section.timeline so the
    shared exporters render the progress ledger — covering every kind mapping."""
    th = _thread(key="a", label="wave0", last_ts=NOW - 1)
    th.add_event(ct.ToolEvent("cmd", "shell", "pytest -q", "ok", None, NOW))
    th.add_event(
        ct.ToolEvent("patch", "patch", "", "error", None, NOW)
    )  # tool_use, no detail
    th.add_event(ct.ToolEvent("think", "reasoning", "planning", "", None, NOW))
    th.add_event(
        ct.ToolEvent("msg", "message", "", "", None, NOW)
    )  # text falls back to label
    src = _seeded_source(tmp_path, th)
    (card,) = src.export_model(src.poll()).blocks
    kinds = [e.kind for e in card.timeline]
    assert kinds == ["tool_use", "tool_use", "thinking", "text"]
    shell, patch, think, msg = card.timeline
    assert shell.name == "shell" and shell.tool_input == {"detail": "pytest -q"}
    assert patch.tool_input == {} and patch.is_error is True  # no detail → empty input
    assert think.text == "planning"
    assert msg.text == "message"  # empty detail → the label


def test_headline_accessor_passthrough(tmp_path):
    src = _seeded_source(tmp_path)
    snap = src.poll()
    assert src.headline(snap) == snap.headline


def test_alert_matrix(tmp_path):
    src = _seeded_source(tmp_path, _thread(aborted=True, last_ts=NOW))
    err = src.alert(src.poll())
    assert err is not None and err.level == "critical"
    assert err.source_id == "codexmon"

    unreachable_src = CodexSource(
        poller=_BoomPoller(str(tmp_path / "s"), str(tmp_path / "r")),
        clock=lambda: NOW,
    )
    warn = unreachable_src.alert(unreachable_src.poll())
    assert warn is not None and warn.level == "warn"
    assert SK_TOKEN not in warn.detail  # alert detail is re-scrubbed

    stalled = Snapshot(
        source_id="codexmon",
        ts=NOW,
        reachable=True,
        stale=False,
        state=SourceState.STALLED,
        headline="h",
        payload=CodexPayload(),
    )
    got = src.alert(stalled)
    assert got is not None and got.level == "warn" and got.detail == ""

    healthy = _seeded_source(tmp_path, _thread(last_ts=NOW))
    assert healthy.alert(healthy.poll()) is None
