"""Branch-coverage completion tests for harness.dispatcher and harness.adapters.

These tests document CURRENT behavior only -- they add NO runtime logic and touch
no source. Each asserts a REAL observable result (dispatch verdict/terminal log,
adapter envelope shape, breaker fail-open, CLI exit code), never coverage padding.

Isolation: every test redirects AGENT_HARNESS_STATE_ROOT (and the two checkpoint
env vars the shadow lane may read) into tmp_path, so nothing here touches the real
home or the live harness state. Platform gates are driven through the public API
with plain values, so both branches run identically on Linux CI and Windows.
"""

from __future__ import annotations

import io
import json
import runpy
import sys
import time

import pytest

import harness.adapters as A
import harness.dispatcher as D
from harness.models import HookResult


@pytest.fixture(autouse=True)
def _isolate_state(tmp_path, monkeypatch):
    """Redirect all harness state under tmp_path and neutralize inherited mode env
    so every test is deterministic regardless of the launching shell."""
    monkeypatch.setenv("AGENT_HARNESS_STATE_ROOT", str(tmp_path / "state"))
    monkeypatch.setenv("BASIC_MEMORY_CHECKPOINT_DIR", str(tmp_path / "checkpoints"))
    monkeypatch.setenv(
        "AGENT_HARNESS_RECALL_INDEX", str(tmp_path / "missing-index.json")
    )
    for var in (
        "HARNESS_INJECT_MIXER",
        "HARNESS_BREAKER_MODE",
        "HARNESS_INJECT_CAP",
        "HARNESS_BREAKER_STREAK",
        "HARNESS_BREAKER_COOLDOWN_SEC",
        "HARNESS_FAILED_SPIKE",
    ):
        monkeypatch.delenv(var, raising=False)


def _raise(exc):
    """Return a callable that ignores its args and raises ``exc`` -- used to force
    the fail-open except paths in storage helpers the dispatcher calls."""

    def _fn(*_args, **_kwargs):
        raise exc

    return _fn


def _event(event_name="PostToolUse", **payload):
    payload.setdefault("session_id", "s")
    return A.normalize_event(payload, provider="codex", event_name=event_name)


# --------------------------------------------------------------------------- #
# dispatcher.py -- pure helpers
# --------------------------------------------------------------------------- #


def test_env_int_falls_back_to_default_on_non_numeric(monkeypatch):
    # 128-129: a set-but-unparseable value -> the floored default, not a crash.
    monkeypatch.setenv("HARNESS_INJECT_CAP", "not-an-int")
    assert D._env_int("HARNESS_INJECT_CAP", 500, 256) == 500
    # floor still applies when the default itself is below the floor
    assert D._env_int("HARNESS_INJECT_CAP", 10, 256) == 256


def test_sterile_cockpit_with_string_command_input():
    # 150->151: tool.input arrives as a bare string; it IS the pending command.
    event = _event("PreToolUse", tool_input="git commit -m wip")
    assert D._pending_command(event) == "git commit -m wip"
    assert D._sterile_cockpit(event) is True


def test_sterile_cockpit_with_non_command_dict_input():
    # 152->154: a dict input with no string 'command' yields '' -> not sterile.
    event = _event("PreToolUse", tool_input={"file_path": "notes.txt"})
    assert D._pending_command(event) == ""
    assert D._sterile_cockpit(event) is False


def test_mix_injections_drops_whitespace_only_after_trim():
    # 180->182: a context longer than the remaining cap that is all-whitespace
    # once trimmed is dropped and the loop breaks (nothing empty is appended).
    out = D.mix_injections(
        [(D.PRIORITY_SAFETY, "secret_literal", "        ")],
        has_safety=True,
        sterile=False,
        total_cap=3,
    )
    assert out == []


def test_emit_shadow_swallows_a_failing_sink(monkeypatch):
    # 231-232: shadow_log is callable but raises; _emit_shadow must not propagate.
    seen = []

    def boom(*args, **_kwargs):
        seen.append(args)
        raise RuntimeError("shadow sink down")

    monkeypatch.setattr(D._modules, "shadow_log", boom)
    D._emit_shadow("injection_mixer", "advisory", _event(), "rc", "detail")
    assert seen  # the sink was actually invoked (try body executed) before it raised


# --------------------------------------------------------------------------- #
# dispatcher.py -- HarnessDispatcher.dispatch module-result handling
# --------------------------------------------------------------------------- #


class _NonResultModule:
    name = "weird"

    def run(self, _event):
        return {"not": "a HookResult"}


def test_module_returning_non_hookresult_fails_open(tmp_path):
    # 278->279: a non-HookResult raises TypeError, caught by the per-module guard.
    disp = D.HarnessDispatcher(modules=[_NonResultModule()], state_root=tmp_path / "st")
    result = disp.dispatch(
        {"session_id": "s"}, provider="codex", event_name="PostToolUse"
    )
    assert result.action == "allow"
    assert result.status.startswith("FAILED:")
    assert result.reason_code == "internal_error"
    log = (tmp_path / "st" / "terminal.jsonl").read_text(encoding="utf-8")
    assert "weird" in log


class _AllowNonOkModule:
    name = "recall"

    def run(self, _event):
        return HookResult.success(action="allow", reason_code="lexical_recall")


def test_allow_action_with_nonok_reason_updates_reason_code(tmp_path):
    # 290->291: action equals the running action ("allow") but reason_code != "ok",
    # so the reason_code is adopted (and NOT overridden, since there is no error).
    disp = D.HarnessDispatcher(
        modules=[_AllowNonOkModule()], state_root=tmp_path / "st"
    )
    result = disp.dispatch(
        {"session_id": "s"}, provider="codex", event_name="PostToolUse"
    )
    assert result.action == "allow"
    assert result.status.startswith("SUCCESS:")
    assert result.reason_code == "lexical_recall"


class _FailedStatusModule:
    name = "memo"

    def run(self, _event):
        return HookResult(
            status="FAILED:memo",
            action="allow",
            reason_code="ok",
            additional_context=[],
        )


def test_module_failed_status_is_recorded_as_error(tmp_path):
    # 292->293-295: a FAILED: status marks had_error, appends the module, and (with
    # action still allow) surfaces as internal_error in the terminal record.
    disp = D.HarnessDispatcher(
        modules=[_FailedStatusModule()], state_root=tmp_path / "st"
    )
    result = disp.dispatch(
        {"session_id": "s"}, provider="codex", event_name="PostToolUse"
    )
    assert result.status.startswith("FAILED:")
    assert result.reason_code == "internal_error"
    log = (tmp_path / "st" / "terminal.jsonl").read_text(encoding="utf-8")
    assert "memo" in log


class _DupBlankContextModule:
    name = "dup"

    def run(self, _event):
        return HookResult.success(
            action="inject",
            reason_code="tool_memo",
            additional_context=["   ", "real note", "real note"],
        )


def test_blank_and_duplicate_contexts_are_skipped(tmp_path):
    # 283->281: a whitespace-only context (empty after strip) and an exact
    # duplicate are both skipped; only the single distinct context survives.
    disp = D.HarnessDispatcher(
        modules=[_DupBlankContextModule()], state_root=tmp_path / "st"
    )
    result = disp.dispatch(
        {"session_id": "s"}, provider="codex", event_name="PostToolUse"
    )
    assert result.action == "inject"
    assert result.additional_context == ["real note"]


# --------------------------------------------------------------------------- #
# dispatcher.py -- F6 circuit-breaker helpers (fail-open bookkeeping)
# --------------------------------------------------------------------------- #


def test_normalize_breaker_coerces_non_dict_state():
    # 381->382: a non-dict persisted breaker is replaced with the empty shape.
    normalized = D.HarnessDispatcher._normalize_breaker([1, 2, 3])
    assert normalized == {"modules": {}, "alerts": []}


def test_load_breaker_falls_open_when_read_raises(tmp_path, monkeypatch):
    # 392-393: an exception reading breaker.json yields the safe empty default.
    disp = D.HarnessDispatcher(modules=[], state_root=tmp_path / "st")
    monkeypatch.setattr(D, "read_json", _raise(RuntimeError("io down")))
    assert disp._load_breaker() == {"modules": {}, "alerts": []}


def test_is_quarantined_handles_unparseable_timestamp(tmp_path):
    # 408-409: a non-numeric quarantined_until must not raise -> treated as False.
    disp = D.HarnessDispatcher(modules=[], state_root=tmp_path / "st")
    state = {"modules": {"m": {"quarantined_until": "not-a-number"}}, "alerts": []}
    assert disp._is_quarantined(state, "m", 123.0) is False


def test_finalize_breaker_skips_non_dict_slot(tmp_path):
    # 450->451: a corrupt (non-dict) module slot is skipped, healthy ones persist.
    disp = D.HarnessDispatcher(modules=[], state_root=tmp_path / "st")
    state = {
        "modules": {
            "bad": "not-a-dict",
            "good": {"streak": 0, "quarantined_until": 0.0},
        },
        "alerts": [],
    }
    disp._finalize_breaker(state, _event(), [], time.time(), "shadow")
    assert (tmp_path / "st" / "breaker.json").exists()


def test_finalize_breaker_write_error_is_fail_open(tmp_path, monkeypatch):
    # 479-481: a persistence error during finalize must never reach the hook.
    disp = D.HarnessDispatcher(modules=[], state_root=tmp_path / "st")
    monkeypatch.setattr(D, "atomic_write_json", _raise(OSError("disk full")))
    # Returns normally (no raise) despite the write blowing up.
    disp._finalize_breaker(
        {"modules": {}, "alerts": []}, _event(), [], time.time(), "shadow"
    )


def test_record_terminal_write_error_is_fail_open(tmp_path):
    # 514-515: if the terminal.jsonl path is unwritable, the record is dropped
    # silently. Make the path a directory so open("a") raises on every platform.
    disp = D.HarnessDispatcher(modules=[], state_root=tmp_path / "st")
    (tmp_path / "st" / "terminal.jsonl").mkdir(parents=True)
    disp._record_terminal(
        HookResult.success(),
        provider="codex",
        event_name="PostToolUse",
        elapsed_ms=1.0,
        failed_modules=[],
    )
    # The path is still the directory we created -- nothing crashed, nothing wrote.
    assert (tmp_path / "st" / "terminal.jsonl").is_dir()


# --------------------------------------------------------------------------- #
# dispatcher.py -- _parse_args + main (ordinary argv/stdin-driven CLI functions)
# --------------------------------------------------------------------------- #


def test_parse_args_returns_namespace(tmp_path):
    # 519-527: the argparse entrypoint parses provider/event/state-root.
    args = D._parse_args(
        ["--provider", "claude", "--event", "PreToolUse", "--state-root", str(tmp_path)]
    )
    assert (args.provider, args.event, args.state_root) == (
        "claude",
        "PreToolUse",
        str(tmp_path),
    )


class _StubDispatcher:
    """Records what main handed it; keeps the main() tests independent of the real
    module set so they exercise ONLY main's parse/dispatch/render/write wiring."""

    last: tuple = ()

    def __init__(self, *, state_root=None):
        self.state_root = state_root

    def dispatch(self, raw, *, provider, event_name):
        _StubDispatcher.last = (raw, provider, event_name)
        return HookResult.success()


def test_main_reads_dict_stdin_and_writes_native_for_terminal_event(
    monkeypatch, capsys, tmp_path
):
    # 531-549,556 + 535->540 + 548->549: a well-formed dict payload is dispatched
    # and, because render produced native output, it is written as one JSON line.
    monkeypatch.setattr(D, "HarnessDispatcher", _StubDispatcher)
    monkeypatch.setattr(
        D,
        "render_output",
        lambda result, *, provider, event_name: {"systemMessage": "hi"},
    )
    monkeypatch.setattr(sys, "stdin", io.StringIO('{"session_id": "s"}'))
    rc = D.main(
        ["--provider", "codex", "--event", "Stop", "--state-root", str(tmp_path)]
    )
    assert rc == 0
    assert _StubDispatcher.last[0] == {"session_id": "s"}
    assert json.loads(capsys.readouterr().out) == {"systemMessage": "hi"}


def test_main_coerces_non_dict_stdin_to_empty(monkeypatch, capsys, tmp_path):
    # 535->536: valid JSON that is not an object is coerced to {}. The Stop/
    # SubagentStop event still forces a write even though native is empty.
    monkeypatch.setattr(D, "HarnessDispatcher", _StubDispatcher)
    monkeypatch.setattr(D, "render_output", lambda result, *, provider, event_name: {})
    monkeypatch.setattr(sys, "stdin", io.StringIO("[1, 2, 3]"))
    rc = D.main(
        [
            "--provider",
            "codex",
            "--event",
            "SubagentStop",
            "--state-root",
            str(tmp_path),
        ]
    )
    assert rc == 0
    assert _StubDispatcher.last[0] == {}
    assert json.loads(capsys.readouterr().out) == {}


def test_main_bad_json_stdin_fails_open_to_empty(monkeypatch, capsys, tmp_path):
    # 537-538: unparseable stdin is swallowed and dispatched as an empty payload.
    monkeypatch.setattr(D, "HarnessDispatcher", _StubDispatcher)
    monkeypatch.setattr(D, "render_output", lambda result, *, provider, event_name: {})
    monkeypatch.setattr(sys, "stdin", io.StringIO("not-json{{{"))
    rc = D.main(
        ["--provider", "codex", "--event", "PreToolUse", "--state-root", str(tmp_path)]
    )
    assert rc == 0
    assert _StubDispatcher.last[0] == {}
    assert capsys.readouterr().out == ""


def test_main_skips_write_when_no_native_and_not_terminal(
    monkeypatch, capsys, tmp_path
):
    # 548->556: empty native output on a non-terminal event emits nothing.
    monkeypatch.setattr(D, "HarnessDispatcher", _StubDispatcher)
    monkeypatch.setattr(D, "render_output", lambda result, *, provider, event_name: {})
    monkeypatch.setattr(sys, "stdin", io.StringIO('{"a": 1}'))
    rc = D.main(
        ["--provider", "codex", "--event", "PreToolUse", "--state-root", str(tmp_path)]
    )
    assert rc == 0
    assert capsys.readouterr().out == ""


def test_main_inner_exception_returns_zero(monkeypatch, capsys, tmp_path):
    # 552-555: a failure after parsing (render raises) is fail-open -> exit 0, no output.
    monkeypatch.setattr(D, "HarnessDispatcher", _StubDispatcher)
    monkeypatch.setattr(D, "render_output", _raise(RuntimeError("render blew up")))
    monkeypatch.setattr(sys, "stdin", io.StringIO('{"a": 1}'))
    rc = D.main(
        ["--provider", "codex", "--event", "Stop", "--state-root", str(tmp_path)]
    )
    assert rc == 0
    assert capsys.readouterr().out == ""


def test_module_main_guard_executes_as_entrypoint(monkeypatch):
    # 559->560: run dispatcher.py as __main__ so the `if __name__ == "__main__"`
    # guard fires for real. With no CLI args, _parse_args (before any try) exits 2
    # via argparse, which propagates through the guard -- exercising the real
    # entrypoint without running the default module set.
    monkeypatch.setattr(sys, "argv", ["dispatcher.py"])
    with pytest.raises(SystemExit) as excinfo:
        runpy.run_path(D.__file__, run_name="__main__")
    assert excinfo.value.code == 2


# --------------------------------------------------------------------------- #
# adapters.py -- normalize_event / render_output edge branches
# --------------------------------------------------------------------------- #


def test_normalize_event_rejects_unsupported_provider():
    # 77->78: an unknown provider is a hard ValueError.
    with pytest.raises(ValueError, match="unsupported provider: gemini"):
        A.normalize_event(
            {"session_id": "s"}, provider="gemini", event_name="PreToolUse"
        )


def test_render_output_rejects_unsupported_provider():
    # 164->165: render also rejects an unknown provider.
    result = HookResult.success(action="inject", additional_context=["x"])
    with pytest.raises(ValueError, match="unsupported provider: gemini"):
        A.render_output(result, provider="gemini", event_name="PreToolUse")


def test_message_uses_continuation_when_no_context():
    # 152->153: with no additional_context, the continuation becomes the message.
    result = HookResult(
        status="SUCCESS:hook",
        action="inject",
        reason_code="goal_reinjection",
        additional_context=[],
        continuation="carry this forward",
    )
    rendered = A.render_output(result, provider="claude", event_name="SessionStart")
    assert rendered == {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": "carry this forward",
        }
    }


def test_block_on_generic_event_renders_decision_block():
    # 178->185: a block on an event that is neither PreToolUse nor PermissionRequest
    # renders the generic {"decision": "block"} shape.
    result = HookResult.success(
        action="block",
        reason_code="secret_literal",
        additional_context=["Blocked for safety."],
    )
    rendered = A.render_output(result, provider="claude", event_name="PostToolUse")
    assert rendered == {"decision": "block", "reason": "Blocked for safety."}


def test_continue_action_renders_block_with_continuation():
    # 187->188: a continue action renders as a block whose reason is the
    # continuation (which wins over the assembled message).
    result = HookResult(
        status="SUCCESS:hook",
        action="continue",
        reason_code="repeated_no_progress",
        additional_context=["some context"],
        continuation="Stop and re-plan.",
    )
    rendered = A.render_output(result, provider="codex", event_name="Stop")
    assert rendered == {"decision": "block", "reason": "Stop and re-plan."}


def test_inject_on_stop_for_claude_renders_additional_context():
    # 198->199: an inject on Stop/SubagentStop for claude (NOT a _CONTEXT_EVENTS
    # member) still renders as native additionalContext.
    result = HookResult.success(
        action="inject",
        reason_code="goal_reinjection",
        additional_context=["Remember the goal."],
    )
    rendered = A.render_output(result, provider="claude", event_name="Stop")
    assert rendered == {
        "hookSpecificOutput": {
            "hookEventName": "Stop",
            "additionalContext": "Remember the goal.",
        }
    }
