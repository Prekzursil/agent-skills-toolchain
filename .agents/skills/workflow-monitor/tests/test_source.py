#!/usr/bin/env python3
"""``wfmon_export.source`` — the WfmonSource adapter behind the monitorcore contract (WU5).

Proves the three WU5 done-signals plus full branch coverage of the adapter:

* **poll never throws** — an injected reader that raises ``Exception`` yields a stale /
  unreachable :class:`Snapshot` with the error text and NO propagation; a ``BaseException``
  (Ctrl-C) is deliberately NOT swallowed.
* **fixture round-trip** — the real ``wf_export00-fixture`` polled through the adapter and
  fed ``export_model`` reproduces PR-A's golden Markdown + HTML byte-for-byte.
* **runtime_checkable** — ``isinstance(WfmonSource(...), MonitorSource)`` holds.
* every reachable / stale / error / running / done / idle branch of the adapter is exercised.
"""

from __future__ import annotations

import os

import pytest

from monitorcore.contract import Alert, MonitorSource, SourceState
from monitorcore.render_html import render_html
from monitorcore.render_md import render_md
from monitorcore.report_doc import ReportDoc
from wfmon_export.model import AgentExport, ExportModel
from wfmon_export.source import WfmonPayload, WfmonSource

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPORT_PROJECTS = os.path.join(HERE, "fixtures", "export", "projects")
REPO = os.path.dirname(os.path.dirname(HERE))
GOLDEN = os.path.join(REPO, "tools", "monitorcore", "tests", "golden")
WF_ID = "wf_export00-fixture"
PINNED = "2026-07-12T00:00:00+00:00"


def _golden(name: str, ext: str) -> str:
    with open(os.path.join(GOLDEN, f"wf_export00.{name}.{ext}"), encoding="utf-8") as f:
        return f.read()


def _model(
    *,
    active: bool,
    running: int = 0,
    done: int = 0,
    error: int = 0,
    idle: int = 0,
    total: int = 0,
    name: str = "Run",
) -> ExportModel:
    """A minimal hand-built ExportModel exercising a single ``_derive_state`` branch."""
    return ExportModel(
        wf_id="wf_x",
        name=name,
        status="running" if active else "completed",
        active=active,
        generated_at=PINNED,
        schema_version="x",
        scope="run",
        scope_agents=[],
        redaction_mode="strict",
        phases=[],
        rollup={
            "running": running,
            "done": done,
            "error": error,
            "idle": idle,
            "total": total,
            "tokens": 0,
        },
        session="s",
        manifest_path="",
        provenance={},
    )


def _reader_returning(model: ExportModel):
    def _reader(wf_id, **kwargs):  # noqa: ANN001, ARG001
        return model

    return _reader


# ───────────────────────── real-fixture round-trip (done-signal) ─────────────────────────
def test_fixture_roundtrips_export_model_to_golden():
    src = WfmonSource(WF_ID, projects=EXPORT_PROJECTS, generated_at=PINNED)
    snap = src.poll()
    assert snap.reachable is True and snap.stale is False
    assert snap.state == SourceState.ERROR  # fixture has one errored agent
    assert snap.error is None
    assert isinstance(snap.payload, WfmonPayload)
    assert snap.payload.model is not None
    assert len(snap.payload.agents) == 3
    assert all(
        isinstance(a, AgentExport) for a in snap.payload.agents
    )  # typed, not flattened

    doc = src.export_model(snap)
    assert isinstance(doc, ReportDoc)
    assert render_md(doc, tools="full", thinking=True, redact=True) == _golden(
        "full", "md"
    )
    assert render_html(doc, tools="full", thinking=True, redact=True) == _golden(
        "full", "html"
    )


def test_fixture_headline_and_native_view():
    src = WfmonSource(WF_ID, projects=EXPORT_PROJECTS, generated_at=PINNED)
    snap = src.poll()
    assert src.headline(snap) == snap.headline
    assert "error" in snap.headline  # coarse state surfaced in the one-liner
    native = src.render_native(snap)
    assert isinstance(native, str) and "wfmon-export-fixture" in native


# ───────────────────────── runtime_checkable (done-signal) ─────────────────────────
def test_isinstance_monitorsource():
    src = WfmonSource(WF_ID, projects=EXPORT_PROJECTS)
    assert isinstance(src, MonitorSource)


# ───────────────────────── poll never throws (done-signal) ─────────────────────────
def test_poll_swallows_exception_returns_unreachable_snapshot():
    def _boom(wf_id, **kwargs):  # noqa: ANN001, ARG001
        raise RuntimeError("manifest gone")

    src = WfmonSource("wf_missing", reader=_boom, clock=lambda: 42.0)
    snap = src.poll()  # MUST NOT raise
    assert snap.reachable is False
    assert snap.stale is True
    assert snap.state == SourceState.UNREACHABLE
    assert snap.error == "manifest gone"
    assert snap.ts == 42.0
    assert snap.payload.model is None  # no prior good poll -> empty typed payload
    assert snap.payload.agents == ()
    assert "unreachable" in snap.headline


def test_poll_does_not_swallow_baseexception():
    def _interrupt(wf_id, **kwargs):  # noqa: ANN001, ARG001
        raise KeyboardInterrupt

    src = WfmonSource("wf", reader=_interrupt)
    with pytest.raises(KeyboardInterrupt):
        src.poll()  # BaseException propagates (guard is `except Exception`, not BaseException)


def test_poll_retains_last_good_payload_when_next_poll_fails():
    good = _model(active=True, running=1, total=1)
    calls = {"n": 0}

    def _flaky(wf_id, **kwargs):  # noqa: ANN001, ARG001
        calls["n"] += 1
        if calls["n"] == 1:
            return good
        raise OSError("read failed")

    src = WfmonSource("wf", reader=_flaky)
    first = src.poll()
    assert first.reachable is True and first.payload.model is good

    second = src.poll()
    assert second.reachable is False and second.stale is True
    assert second.state == SourceState.UNREACHABLE
    assert second.payload.model is good  # last-good payload retained
    assert second.error == "read failed"


# ───────────────────────── coarse-state derivation (every branch) ─────────────────────────
@pytest.mark.parametrize(
    "model,expected",
    [
        (_model(active=True, error=2, total=3), SourceState.ERROR),
        (_model(active=True, running=1, total=1), SourceState.RUNNING),
        (_model(active=False, done=1, total=1), SourceState.DONE),
        (_model(active=True, idle=1, total=1), SourceState.IDLE),
    ],
)
def test_derive_state_branches(model, expected):
    src = WfmonSource("wf", reader=_reader_returning(model))
    assert src.poll().state == expected


# ───────────────────────── render_native / export_model fallbacks (model None) ─────────────
def test_unreachable_native_and_export_fallbacks():
    def _boom(wf_id, **kwargs):  # noqa: ANN001, ARG001
        raise RuntimeError("x")

    src = WfmonSource("wf_none", reader=_boom)
    snap = src.poll()
    # render_native falls back to the headline when there is no model
    assert src.render_native(snap) == snap.headline
    # export_model returns a minimal ReportDoc (never raises) when there is no model
    doc = src.export_model(snap)
    assert isinstance(doc, ReportDoc)
    assert doc.title == "wfmon"
    assert doc.generated_at == ""


# ───────────────────────── alert() classification (signature-only) ─────────────────────────
def test_alert_critical_on_error():
    src = WfmonSource(
        "wf", reader=_reader_returning(_model(active=True, error=1, total=1))
    )
    alert = src.alert(src.poll())
    assert isinstance(alert, Alert)
    assert alert.level == "critical"
    assert alert.source_id == "wfmon"


def test_alert_warn_on_unreachable():
    def _boom(wf_id, **kwargs):  # noqa: ANN001, ARG001
        raise RuntimeError("nope")

    src = WfmonSource("wf", reader=_boom)
    alert = src.alert(src.poll())
    assert isinstance(alert, Alert)
    assert alert.level == "warn"
    assert alert.detail == "nope"


def test_alert_none_on_healthy_states():
    src = WfmonSource(
        "wf", reader=_reader_returning(_model(active=True, running=1, total=1))
    )
    assert src.alert(src.poll()) is None
