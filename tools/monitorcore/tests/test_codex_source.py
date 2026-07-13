"""Fixture-backed contract tests for the Codex rollout ``MonitorSource`` adapter."""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

from monitorcore.codex_source import (
    CodexPayload,
    CodexSource,
    CodexToolCall,
    _parse_iso,
    default_sessions_dir,
    latest_rollout_path,
    main,
    read_latest_rollout,
    read_rollout,
)
from monitorcore.contract import Alert, MonitorSource, Snapshot, SourceState
from monitorcore.render_html import render_html
from monitorcore.render_md import render_md
from monitorcore.report_doc import ReportDoc, Section, Table

FIXTURE = Path(__file__).parent / "fixtures" / "codex" / "rollout-sample.jsonl"


def _line(outer: str, payload: dict, timestamp: str = "2026-07-14T00:00:00Z") -> str:
    return json.dumps({"timestamp": timestamp, "type": outer, "payload": payload})


def _write_rollout(path: Path, *lines: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _sample_tree(tmp_path: Path) -> tuple[Path, Path]:
    sessions = tmp_path / "sessions"
    older = _write_rollout(
        sessions / "2026" / "07" / "13" / "rollout-older.jsonl",
        _line("session_meta", {"session_id": "older"}),
    )
    newest = sessions / "2026" / "07" / "14" / "rollout-newest.jsonl"
    newest.parent.mkdir(parents=True)
    shutil.copyfile(FIXTURE, newest)
    os.utime(older, (100.0, 100.0))
    os.utime(newest, (200.0, 200.0))
    return sessions, newest


def _snapshot(payload: CodexPayload, state: SourceState) -> Snapshot[CodexPayload]:
    return Snapshot(
        source_id="codex",
        ts=42.0,
        reachable=True,
        stale=False,
        state=state,
        headline=f"codex [{state}]",
        payload=payload,
    )


def test_fixture_poll_selects_newest_and_maps_aborted_to_failed(tmp_path):
    sessions, newest = _sample_tree(tmp_path)
    final_ts = datetime.fromisoformat("2026-07-14T00:01:00+00:00").timestamp()
    source = CodexSource(sessions_dir=sessions, clock=lambda: final_ts + 60)

    assert isinstance(source, MonitorSource)
    snap = source.poll()

    assert snap.reachable is True and snap.stale is False
    assert snap.state == SourceState.ERROR
    assert snap.payload.path == str(newest)
    assert snap.payload.session_id == "session-sample"
    assert snap.payload.cwd == r"C:\work\sample"
    assert snap.payload.model == "gpt-5.4"
    assert snap.payload.prompt == "Build the synthetic adapter fixture"
    assert snap.payload.last_message == "Working on the adapter"
    assert snap.payload.turns == 1
    assert snap.payload.status == "failed"
    assert snap.payload.total_tokens == 150_000
    assert snap.payload.context_tokens == 50_000
    assert snap.payload.context_window == 200_000
    assert snap.payload.context_percent == 25
    assert len(snap.payload.tool_calls) == 4
    assert snap.age_s == 60.0
    assert snap.error is None
    assert "failed" in snap.headline

    native = source.render_native(snap)
    assert "ctx 25%" in native
    assert "150000" in native
    assert "tools: 4" in native
    assert "Build the synthetic adapter fixture" in native

    alert = source.alert(snap)
    assert isinstance(alert, Alert)
    assert alert.level == "critical"


def test_fixture_export_uses_shared_report_renderers(tmp_path):
    sessions, _newest = _sample_tree(tmp_path)
    source = CodexSource(sessions_dir=sessions, clock=lambda: 42.0)
    snap = source.poll()

    doc = source.export_model(snap)

    assert isinstance(doc, ReportDoc)
    assert doc.active is False
    assert doc.title == "Codex session session-sample"
    assert isinstance(doc.blocks[0], Section)
    card = doc.blocks[0].children[0]
    assert isinstance(card, Section) and card.card is True
    assert card.badge == "error"
    assert card.tokens == 150_000
    assert card.tool_calls == 4
    assert isinstance(doc.blocks[1].children[0], Table)
    assert "ctx 25%" in card.lead

    markdown = render_md(doc)
    html = render_html(doc)
    assert "Build the synthetic adapter fixture" in markdown
    assert "Build the synthetic adapter fixture" in html


def test_export_redacts_path_and_tool_detail_before_nonredacting_fields():
    home = str(Path.home())
    payload = CodexPayload(
        path=str(Path.home() / "private" / "rollout.jsonl"),
        session_id="s",
        status="done",
        tool_calls=(
            # Table cells have no renderer-level redact flag, so scrub them in the adapter.
            CodexToolCall(
                kind="command",
                label="read",
                detail=str(Path.home() / "private.txt"),
            ),
        ),
    )
    doc = CodexSource().export_model(_snapshot(payload, SourceState.DONE))
    table = doc.blocks[1].children[0]

    assert isinstance(table, Table)
    assert home not in dict(doc.meta)["Path"]
    assert home not in table.rows[0][3]


@pytest.mark.parametrize(
    "terminal,expected_status,expected_state",
    [
        (None, "running", SourceState.RUNNING),
        ("task_complete", "done", SourceState.DONE),
        ("turn_aborted", "failed", SourceState.ERROR),
    ],
)
def test_lifecycle_states(terminal, expected_status, expected_state, tmp_path):
    lines = [
        _line("session_meta", {"session_id": "s"}),
        _line("event_msg", {"type": "task_started"}),
    ]
    if terminal:
        lines.append(_line("event_msg", {"type": terminal}))
    path = _write_rollout(
        tmp_path / "sessions" / "2026" / "07" / "14" / "rollout-state.jsonl",
        *lines,
    )

    payload = read_rollout(path)
    snap = CodexSource(sessions_dir=tmp_path / "sessions", clock=lambda: 1.0).poll()

    assert payload.status == expected_status
    assert snap.state == expected_state


def test_new_task_clears_prior_abort_and_completion(tmp_path):
    path = _write_rollout(
        tmp_path / "rollout-reset.jsonl",
        _line("event_msg", {"type": "task_started"}),
        _line("event_msg", {"type": "task_complete"}),
        _line("event_msg", {"type": "turn_aborted"}),
        _line("event_msg", {"type": "task_started"}),
    )

    payload = read_rollout(path)

    assert payload.turns == 2
    assert payload.status == "running"


def test_reachable_session_without_started_task_is_idle(tmp_path):
    path = _write_rollout(
        tmp_path / "rollout-idle.jsonl",
        _line("session_meta", {"session_id": "idle"}),
    )
    assert read_rollout(path).status == "idle"


def test_started_task_becomes_idle_after_silence_threshold(tmp_path):
    timestamp = "2026-07-14T00:00:00Z"
    event_ts = datetime.fromisoformat("2026-07-14T00:00:00+00:00").timestamp()
    path = _write_rollout(
        tmp_path / "sessions" / "2026" / "07" / "14" / "rollout-idle.jsonl",
        _line("event_msg", {"type": "task_started"}, timestamp),
    )
    source = CodexSource(
        sessions_dir=tmp_path / "sessions",
        idle_s=12.0,
        clock=lambda: event_ts + 12.0,
    )

    snap = source.poll()

    assert snap.payload.path == str(path)
    assert snap.payload.status == "idle"
    assert snap.state == SourceState.IDLE


def test_parser_handles_errors_unknowns_and_all_tool_statuses(tmp_path):
    path = _write_rollout(
        tmp_path / "rollout-branches.jsonl",
        "not json",
        "[]",
        "",
        _line("unknown", {"model": "gpt-x"}, "bad-time"),
        _line("session_meta", {"id": "fallback-id", "context_window": 10}),
        _line("turn_context", {"cwd": "/tmp/work", "model": "gpt-y"}),
        _line("event_msg", {"type": "user_message", "message": "first"}),
        _line("event_msg", {"type": "user_message", "message": "second"}),
        _line("event_msg", {"type": "agent_message", "message": "answer"}),
        _line(
            "event_msg",
            {
                "type": "token_count",
                "info": {
                    "total_token_usage": {"total_tokens": 99},
                    "last_token_usage": {"total_tokens": 11},
                    "model_context_window": 22,
                },
            },
        ),
        _line(
            "event_msg",
            {
                "type": "mcp_tool_call_end",
                "invocation": {"server": "s", "tool": "t"},
                "duration": {"secs": 2, "nanos": 0},
                "result": {"Err": "no"},
            },
        ),
        _line("event_msg", {"type": "patch_apply_end", "success": False}),
        _line(
            "response_item",
            {"type": "custom_tool_call", "name": "a", "input": "1", "status": ""},
        ),
        _line(
            "response_item",
            {
                "type": "custom_tool_call",
                "name": "b",
                "input": "2",
                "status": "in_progress",
            },
        ),
        _line(
            "response_item",
            {"type": "custom_tool_call", "name": "c", "input": "3", "status": "failed"},
        ),
        _line(
            "response_item",
            {"type": "function_call", "name": "fn", "arguments": "{}"},
        ),
        _line("response_item", {"type": "reasoning"}),
    )

    payload = read_rollout(path)

    assert payload.session_id == "fallback-id"
    assert payload.model == "gpt-y"
    assert payload.cwd == "/tmp/work"
    assert payload.prompt == "first"
    assert payload.last_message == "answer"
    assert payload.total_tokens == 99
    assert payload.context_tokens == 11
    assert payload.context_percent == 50
    assert [call.status for call in payload.tool_calls] == [
        "error",
        "error",
        "running",
        "running",
        "failed",
        "ok",
    ]
    assert payload.tool_calls[0].duration_s == 2.0


def test_missing_or_invalid_token_values_preserve_safe_defaults(tmp_path):
    path = _write_rollout(
        tmp_path / "rollout-token-defaults.jsonl",
        _line("event_msg", {"type": "token_count", "info": None}),
        _line(
            "event_msg",
            {
                "type": "token_count",
                "info": {
                    "total_token_usage": {"total_tokens": "bad"},
                    "last_token_usage": {"total_tokens": "bad"},
                    "model_context_window": "bad",
                },
            },
        ),
    )
    payload = read_rollout(path)
    assert (payload.total_tokens, payload.context_tokens, payload.context_window) == (
        0,
        0,
        0,
    )
    assert payload.context_percent is None


def test_parser_ignores_invalid_metadata_and_unknown_event_message(tmp_path):
    path = _write_rollout(
        tmp_path / "rollout-invalid-metadata.jsonl",
        _line(
            "session_meta",
            {"session_id": 0, "id": 0, "cwd": 0, "context_window": "bad"},
        ),
        # A repeated session record exercises the already-established start-time path.
        _line("session_meta", {"session_id": "valid"}),
        _line("turn_context", {"cwd": 0}),
        _line("event_msg", {"type": "agent_message", "message": 0}),
        _line("event_msg", {"type": "future_event"}),
    )

    payload = read_rollout(path)

    assert payload.session_id == "valid"
    assert payload.cwd == ""
    assert payload.last_message == ""


def test_task_started_numeric_timestamp_is_start_fallback(tmp_path):
    path = _write_rollout(
        tmp_path / "rollout-numeric-start.jsonl",
        json.dumps(
            {
                "type": "event_msg",
                "payload": {"type": "task_started", "started_at": 123.5},
            }
        ),
    )
    assert read_rollout(path).started_at == 123.5


def test_context_percent_clamps_and_handles_zero_window():
    assert CodexPayload(context_tokens=1, context_window=0).context_percent is None
    assert CodexPayload(context_tokens=250, context_window=100).context_percent == 100
    assert CodexPayload(context_tokens=-1, context_window=100).context_percent == 0


def test_parse_iso_is_total():
    assert _parse_iso("2026-07-14T00:00:00Z") is not None
    assert _parse_iso(123) is None
    assert _parse_iso("") is None
    assert _parse_iso("not-a-time") is None


def test_latest_rollout_path_errors_when_none(tmp_path):
    with pytest.raises(FileNotFoundError, match="rollout"):
        latest_rollout_path(tmp_path)


def test_latest_rollout_skips_stat_failure_and_tiebreaks_by_path(tmp_path, monkeypatch):
    sessions = tmp_path / "sessions"
    a = _write_rollout(
        sessions / "2026" / "07" / "14" / "rollout-a.jsonl",
        _line("session_meta", {"session_id": "a"}),
    )
    b = _write_rollout(
        sessions / "2026" / "07" / "14" / "rollout-b.jsonl",
        _line("session_meta", {"session_id": "b"}),
    )
    broken = _write_rollout(
        sessions / "2026" / "07" / "14" / "rollout-broken.jsonl",
        _line("session_meta", {"session_id": "broken"}),
    )
    os.utime(a, (100.0, 100.0))
    os.utime(b, (100.0, 100.0))
    real_stat = Path.stat

    def _stat(path, *args, **kwargs):
        if path == broken:
            raise OSError("gone")
        return real_stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", _stat)
    assert latest_rollout_path(sessions) == b
    assert read_latest_rollout(sessions).session_id == "b"


def test_poll_swallows_exception_and_retains_last_good_payload():
    good = CodexPayload(path="p", session_id="s", status="done")
    calls = {"count": 0}

    def _flaky(_sessions):
        calls["count"] += 1
        if calls["count"] == 1:
            return good
        raise OSError("read failed")

    source = CodexSource(reader=_flaky, clock=lambda: 42.0)
    first = source.poll()
    second = source.poll()

    assert first.payload is good and first.state == SourceState.DONE
    assert second.reachable is False and second.stale is True
    assert second.state == SourceState.UNREACHABLE
    assert second.payload is good
    assert second.error == "read failed"
    assert "unreachable" in second.headline
    assert "[unreachable]" in source.render_native(second)


def test_first_poll_failure_has_empty_payload_and_fallback_render_export_alert():
    def _boom(_sessions):
        raise RuntimeError("missing")

    source = CodexSource(reader=_boom, clock=lambda: 42.0)
    snap = source.poll()

    assert snap.payload == CodexPayload()
    assert source.render_native(snap) == snap.headline
    doc = source.export_model(snap)
    assert doc == ReportDoc(title="codex", generated_at="", subtitle=snap.headline)
    alert = source.alert(snap)
    assert isinstance(alert, Alert) and alert.level == "warn"
    assert alert.detail == "missing"


def test_poll_does_not_swallow_baseexception():
    def _interrupt(_sessions):
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        CodexSource(reader=_interrupt).poll()


def test_healthy_alerts_and_contextless_native_export():
    payload = CodexPayload(
        path="p",
        session_id="s",
        prompt="prompt",
        status="running",
        turns=1,
    )
    source = CodexSource(reader=lambda _sessions: payload, clock=lambda: 42.0)
    snap = source.poll()

    assert source.alert(snap) is None
    assert source.headline(snap) == snap.headline
    assert "ctx" not in source.render_native(snap)
    assert source.export_model(snap).active is True

    stalled = _snapshot(payload, SourceState.STALLED)
    alert = source.alert(stalled)
    assert isinstance(alert, Alert) and alert.level == "warn"


def test_default_sessions_dir_prefers_codex_home(monkeypatch, tmp_path):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    assert default_sessions_dir() == tmp_path / "sessions"


def test_default_sessions_dir_uses_user_home(monkeypatch, tmp_path):
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert default_sessions_dir() == tmp_path / ".codex" / "sessions"


def test_main_once_uses_fixture_and_shared_live_runner(tmp_path):
    sessions, _newest = _sample_tree(tmp_path)
    out = io.StringIO()

    assert main(["--sessions-dir", str(sessions), "--once"], out=out) == 0
    assert "session-sample" in out.getvalue()
    assert "ctx 25%" in out.getvalue()


def test_deployed_wrapper_runs_vendored_adapter_once(tmp_path):
    sessions, _newest = _sample_tree(tmp_path)
    repo = Path(__file__).resolve().parents[3]
    wrapper = repo / "skills" / "workflow-monitor" / "codex_monitor.py"

    completed = subprocess.run(
        [
            sys.executable,
            str(wrapper),
            "--sessions-dir",
            str(sessions),
            "--once",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "CODEX THREAD [failed] session-sample" in completed.stdout
    assert "ctx 25%" in completed.stdout


def test_main_reads_sys_argv_and_rejects_nonpositive_interval(monkeypatch):
    monkeypatch.setattr("sys.argv", ["codex_monitor.py", "--interval", "0"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2


def test_main_rejects_nonpositive_idle_threshold():
    with pytest.raises(SystemExit) as exc:
        main(["--idle", "0", "--once"])
    assert exc.value.code == 2
