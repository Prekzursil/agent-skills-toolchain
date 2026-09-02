"""Unit tests for hooks.posttool — the thin PostToolUse / longrun shell.

Every I/O seam (stdin, env, clock, the register call, the dedup file) is
injected, so the whole shell reaches 100 % branch coverage without a real hook
harness: event parsing, the elapsed/kind derivations, the fail-open guards, the
dedup persistence, and the register-on-attach path.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from hooks import posttool
from hooks.posttool import (
    ENV_REGISTRY,
    ENV_STATE,
    _elapsed,
    _env_flag,
    _run,
    classify_kind,
    extract_op,
    load_seen,
    main,
    run_hook,
    save_seen,
)


# --------------------------------------------------------------------------- helpers
def _event(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "op_id": "op1",
        "op_kind": "longrun",
        "log_path": "/logs/run.log",
        "elapsed_s": 120.0,
    }
    base.update(overrides)
    return base


class _Recorder:
    """A fake register_fn that records its calls and returns a canned envelope."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, object, str]] = []

    def __call__(
        self,
        template: str,
        task_id: str,
        config: dict[str, object] | None = None,
        *,
        registry: str = "",
    ) -> dict[str, object]:
        self.calls.append((template, task_id, config, registry))
        return {"ok": True, "task": {"id": task_id}}


# --------------------------------------------------------------------------- _env_flag
def test_env_flag_truthy_values():
    assert _env_flag({"K": "1"}, "K") is True
    assert _env_flag({"K": "  TrUe "}, "K") is True


def test_env_flag_falsey_and_missing():
    assert _env_flag({"K": "no"}, "K") is False
    assert _env_flag({}, "K") is False


# --------------------------------------------------------------------------- _elapsed
def test_elapsed_explicit():
    assert _elapsed({"elapsed_s": 42.0}, None) == 42.0


def test_elapsed_bool_is_ignored_then_started_at():
    # A JSON bool must NOT be read as elapsed (isinstance-bool guard); the
    # started_at + now path takes over.
    assert _elapsed({"elapsed_s": True, "started_at": 50.0}, 200.0) == 150.0


def test_elapsed_started_without_now_is_zero():
    assert _elapsed({"started_at": 50.0}, None) == 0.0


def test_elapsed_started_bool_is_zero():
    assert _elapsed({"started_at": True}, 200.0) == 0.0


def test_elapsed_missing_everything_is_zero():
    assert _elapsed({}, 200.0) == 0.0


# --------------------------------------------------------------------------- classify_kind
def test_classify_kind_explicit():
    assert classify_kind({"op_kind": "workflow"}) == "workflow"


def test_classify_kind_bash_background():
    event = {"tool_name": "Bash", "tool_input": {"run_in_background": True}}
    assert classify_kind(event) == "bash-background"


def test_classify_kind_bash_foreground_falls_back_to_tool_name():
    event = {"tool_name": "Bash", "tool_input": {"run_in_background": False}}
    assert classify_kind(event) == "bash"


def test_classify_kind_non_mapping_tool_input():
    assert classify_kind({"tool_name": "Read", "tool_input": None}) == "read"


def test_classify_kind_empty():
    assert classify_kind({}) == ""


# --------------------------------------------------------------------------- extract_op
def test_extract_op_valid():
    op = extract_op(_event(), now=None)
    assert op is not None
    assert op.op_id == "op1" and op.op_kind == "longrun"
    assert op.elapsed_s == 120.0 and op.log_path == "/logs/run.log"


def test_extract_op_missing_op_id():
    assert extract_op(_event(op_id="")) is None


def test_extract_op_missing_log_path():
    assert extract_op(_event(log_path="")) is None


# --------------------------------------------------------------------------- load_seen / save_seen
def test_load_seen_missing_file(tmp_path: Path):
    assert load_seen(str(tmp_path / "nope.json")) == set()


def test_load_seen_malformed(tmp_path: Path):
    path = tmp_path / "seen.json"
    path.write_text("{not-json", encoding="utf-8")
    assert load_seen(str(path)) == set()


def test_load_seen_list(tmp_path: Path):
    path = tmp_path / "seen.json"
    path.write_text(json.dumps(["a", "b"]), encoding="utf-8")
    assert load_seen(str(path)) == {"a", "b"}


def test_load_seen_non_list_json(tmp_path: Path):
    path = tmp_path / "seen.json"
    path.write_text(json.dumps({"a": 1}), encoding="utf-8")
    assert load_seen(str(path)) == set()


def test_save_seen_roundtrip_creates_parent(tmp_path: Path):
    path = tmp_path / "sub" / "seen.json"
    save_seen(str(path), {"x", "y"})
    assert load_seen(str(path)) == {"x", "y"}
    assert json.loads(path.read_text(encoding="utf-8")) == ["x", "y"]  # sorted


# --------------------------------------------------------------------------- run_hook
def test_run_hook_not_attachable():
    out = run_hook(_event(op_id=""), seen=set(), register_fn=_Recorder())
    assert out == {"attached": False, "reason": "not-attachable"}


def test_run_hook_rejected_below_threshold():
    rec = _Recorder()
    seen: set[str] = set()
    out = run_hook(_event(elapsed_s=5.0), seen=seen, register_fn=rec)
    assert out["attached"] is False and out["reason"] == "below-threshold"
    assert out["op_id"] == "op1"
    assert rec.calls == [] and seen == set()  # nothing registered, nothing deduped


def test_run_hook_attaches_and_registers():
    rec = _Recorder()
    seen: set[str] = set()
    out = run_hook(_event(), seen=seen, register_fn=rec, registry="my.toml")
    assert out["attached"] is True and out["reason"] == "attach"
    assert out["registered"] == {"ok": True, "task": {"id": "op1"}}
    assert rec.calls == [
        ("generic-logfile", "op1", {"path": "/logs/run.log"}, "my.toml")
    ]
    assert seen == {"longrun:op1"}


def test_run_hook_killswitch():
    rec = _Recorder()
    out = run_hook(_event(), seen=set(), register_fn=rec, killswitch=True)
    assert out["attached"] is False and out["reason"] == "killswitch"
    assert rec.calls == []


def test_run_hook_default_register_fn_registers_for_real(tmp_path: Path):
    # Exercise the bound default register_fn (mcp_server.logic.register_task)
    # end-to-end against a temp registry, mirroring the logic-test pattern.
    registry = str(tmp_path / "taskwatch.toml")
    seen: set[str] = set()
    out = run_hook(_event(), seen=seen, registry=registry)
    assert out["attached"] is True
    registered = out["registered"]
    assert isinstance(registered, dict) and registered["ok"] is True
    assert Path(registry).exists() and seen == {"longrun:op1"}


# --------------------------------------------------------------------------- _run
def test_run_parse_error_is_fail_open():
    assert _run(io.StringIO("{not json"), {}, None) == 0


def test_run_non_mapping_event_is_fail_open():
    assert _run(io.StringIO("123"), {}, None) == 0


def test_run_attaches_and_saves(tmp_path: Path):
    registry = str(tmp_path / "reg.toml")
    state = str(tmp_path / "seen.json")
    env = {ENV_REGISTRY: registry, ENV_STATE: state}
    rc = _run(io.StringIO(json.dumps(_event())), env, now=1000.0)
    assert rc == 0
    assert Path(registry).exists()
    assert load_seen(state) == {"longrun:op1"}


def test_run_no_attach_does_not_write_state(tmp_path: Path):
    state = str(tmp_path / "seen.json")
    env = {ENV_STATE: state}
    # Below threshold → not attached → dedup file is never written.
    rc = _run(io.StringIO(json.dumps(_event(elapsed_s=1.0))), env, now=1000.0)
    assert rc == 0 and not Path(state).exists()


def test_run_now_none_uses_wall_clock():
    # now=None takes the time.time() branch; a below-threshold event keeps it
    # side-effect free (no registry/state env → defaults, but no attach).
    assert _run(io.StringIO(json.dumps(_event(elapsed_s=0.0))), {}, None) == 0


# --------------------------------------------------------------------------- main
def test_main_normal_path(tmp_path: Path):
    registry = str(tmp_path / "reg.toml")
    state = str(tmp_path / "seen.json")
    env = {ENV_REGISTRY: registry, ENV_STATE: state}
    rc = main(stdin=io.StringIO(json.dumps(_event())), env=env, now=1000.0)
    assert rc == 0 and Path(registry).exists()


def test_main_fail_open_on_unexpected_error(monkeypatch: pytest.MonkeyPatch):
    def _boom(_stream: object, _env: object, _now: object) -> int:
        raise RuntimeError("kaboom")

    monkeypatch.setattr(posttool, "_run", _boom)
    assert main(stdin=io.StringIO("{}"), env={}) == 0


def test_main_defaults_use_stdin_and_environ(monkeypatch: pytest.MonkeyPatch):
    # Cover the stdin=None (sys.stdin) and env=None (os.environ) defaults; a
    # malformed stream makes it a clean, side-effect-free fail-open exit.
    monkeypatch.setattr(posttool.sys, "stdin", io.StringIO("{not json"))
    assert main() == 0
