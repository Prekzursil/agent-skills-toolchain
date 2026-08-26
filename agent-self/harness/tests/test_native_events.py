from __future__ import annotations

import dataclasses
import json
import os
import subprocess
import sys
from pathlib import Path

from harness.adapters import (
    _CONTEXT_EVENTS,
    _NO_NATIVE_CONTEXT_EVENTS,
    normalize_event,
    render_output,
)
from harness.models import HookEvent, HookResult
from harness.registration import EVENTS, _NO_MATCHER, _TIMEOUTS, build_hooks
from harness import registration as _registration

# Layout-independent expected dispatcher path (see the note in
# test_dispatcher_and_registration.py): matches BOTH the live ".agents/harness"
# install and this enshrined "ci/harness" copy, since build_hooks derives it from
# registration.py's own location.
_DISPATCHER = (
    Path(_registration.__file__).resolve().parent / "dispatcher.py"
).as_posix()


# The native events this lane wires (SI-3). PostCompact was already hook-
# registered but needs the adapter/context fix; the rest are the new names.
NEW_EVENTS = (
    "PermissionDenied",
    "PostToolUseFailure",
    "ConfigChange",
    "TaskCreated",
    "TaskCompleted",
    "TeammateIdle",
)

CONTEXT_NEW_EVENTS = ("PostToolUseFailure",)
SYSTEM_MESSAGE_EVENTS = (
    "PostCompact",
    "TaskCompleted",
    "TaskCreated",
    "TeammateIdle",
    "PermissionDenied",
    "ConfigChange",
)


# --------------------------------------------------------------------------
# registration.py: EVENTS / _TIMEOUTS / build_hooks stay coherent (no drift).
# --------------------------------------------------------------------------


def test_events_registers_every_new_native_name():
    for name in NEW_EVENTS:
        assert name in EVENTS, name


def test_every_event_has_a_timeout_so_build_hooks_never_keyerrors():
    assert set(_TIMEOUTS) == set(EVENTS)
    for name in EVENTS:
        assert isinstance(_TIMEOUTS[name], int)
        assert 1 <= _TIMEOUTS[name] <= 10  # small timeouts only


def test_hot_path_events_keep_the_measured_five_second_budget():
    for name in (
        "UserPromptSubmit",
        "PreToolUse",
        "PermissionRequest",
        "PermissionDenied",
        "PostToolUse",
        "PostToolUseFailure",
        "SubagentStop",
        "Stop",
    ):
        assert _TIMEOUTS[name] == 5


def test_build_hooks_generates_matching_block_per_new_event():
    for provider in ("claude", "codex"):
        hooks = build_hooks(provider)
        # codex stays exactly EVENTS; claude additionally folds in the live
        # hand-edited WorktreeCreate/WorktreeRemove keys (FIX 3), so assert
        # containment there. NEW_EVENTS are all standard dispatcher events,
        # unaffected by the claude hand-edits (checked in test_dispatcher_and_
        # registration.py::test_claude_build_hooks_folds_in_live_settings_hand_edits).
        if provider == "codex":
            assert tuple(hooks) == EVENTS
        else:
            assert set(EVENTS) <= set(hooks)
        for name in NEW_EVENTS:
            groups = hooks[name]
            assert len(groups) == 1
            group = groups[0]
            assert len(group["hooks"]) == 1
            hook = group["hooks"][0]
            assert hook["type"] == "command"
            assert (
                hook["command"]
                .replace("\\", "/")
                .endswith(f'/dispatcher.py" --provider {provider} --event {name}')
            )
            assert _DISPATCHER in hook["command"].replace("\\", "/")
            assert hook["timeout"] == _TIMEOUTS[name]
            assert hook["statusMessage"] == f"Shared harness: {name}"
            # Every new event carries the `.*` matcher (none are no-matcher).
            assert name not in _NO_MATCHER
            assert group["matcher"] == ".*"


# --------------------------------------------------------------------------
# adapters.py: normalize_event is tolerant, mapping new payloads onto EXISTING
# HookEvent fields only (no new models.py field).
# --------------------------------------------------------------------------


def test_models_hookevent_has_no_new_fields():
    # HARD RULE (SI-3): the native-wiring lane never touches models.py, so the
    # HookEvent contract must remain exactly these fields. The one recorded
    # exception is J10 (sensitive-artifact report), which added transcript_path as a
    # reviewed change — the module reads the transcript it is asked to classify.
    # This stays an EXACT set so the next unreviewed field still fails here.
    names = {f.name for f in dataclasses.fields(HookEvent)}
    assert names == {
        "schema_version",
        "provider",
        "event",
        "session_id",
        "turn_id",
        "cwd",
        "permission_mode",
        "tool",
        "last_assistant_message",
        "prompt",
        "source",
        "trigger",
        "transcript_path",
        "agent",
    }


def test_post_tool_use_failure_error_maps_onto_tool_result():
    event = normalize_event(
        {
            "session_id": "s",
            "tool_name": "Bash",
            "tool_input": {"command": "pytest -q"},
            "error": "command exited 1",
        },
        provider="claude",
        event_name="PostToolUseFailure",
    )
    assert event.event == "PostToolUseFailure"
    assert event.tool.name == "Bash"
    assert event.tool.input == {"command": "pytest -q"}
    assert event.tool.result == "command exited 1"


def test_standard_result_still_wins_over_failure_aliases():
    # Regression guard: existing tool_response resolution is unchanged.
    event = normalize_event(
        {
            "tool_name": "Bash",
            "tool_response": {"exit_code": 1, "output": "boom"},
            "error": "ignored because tool_response is present",
        },
        provider="codex",
        event_name="PostToolUseFailure",
    )
    assert event.tool.result == {"exit_code": 1, "output": "boom"}


def test_permission_denied_reason_maps_onto_tool_result():
    event = normalize_event(
        {
            "tool_name": "Bash",
            "tool_input": {"command": "rm -rf /"},
            "permission_decision_reason": "denied by policy",
        },
        provider="claude",
        event_name="PermissionDenied",
    )
    assert event.tool.result == "denied by policy"


def test_task_completed_maps_identity_and_summary_onto_agent_and_message():
    event = normalize_event(
        {
            "session_id": "s",
            "task_id": "task-7",
            "task_type": "reviewer",
            "summary": "verified coverage at task close",
        },
        provider="claude",
        event_name="TaskCompleted",
    )
    assert event.agent.id == "task-7"
    assert event.agent.type == "reviewer"
    assert event.last_assistant_message == "verified coverage at task close"


def test_teammate_idle_maps_teammate_identity_and_transcript():
    event = normalize_event(
        {
            "teammate_id": "mate-3",
            "teammate": "builder",
            "transcript_path": "C:/tmp/mate.jsonl",
        },
        provider="codex",
        event_name="TeammateIdle",
    )
    assert event.agent.id == "mate-3"
    assert event.agent.type == "builder"
    assert event.agent.transcript_path == "C:/tmp/mate.jsonl"


def test_task_created_maps_transcript_path_onto_agent():
    event = normalize_event(
        {"task_id": "t9", "transcript_path": "C:/tmp/task.jsonl"},
        provider="claude",
        event_name="TaskCreated",
    )
    assert event.agent.transcript_path == "C:/tmp/task.jsonl"


def test_config_change_normalizes_without_error():
    event = normalize_event(
        {"session_id": "s", "path": "C:/Users/x/.claude/settings.json"},
        provider="claude",
        event_name="ConfigChange",
    )
    assert event.event == "ConfigChange"
    # No mapping asserted — the sentinel handler (another lane) reads cwd etc.
    assert event.tool.name == ""


def test_explicit_agent_id_still_beats_task_alias():
    # Regression guard: an event carrying BOTH agent_id and task_id keeps
    # agent_id (SubagentStop behavior is unchanged).
    event = normalize_event(
        {
            "agent_id": "real-agent",
            "task_id": "should-not-win",
            "agent_type": "reviewer",
            "agent_transcript_path": "C:/tmp/a.jsonl",
        },
        provider="codex",
        event_name="SubagentStop",
    )
    assert event.agent.id == "real-agent"
    assert event.agent.type == "reviewer"
    assert event.agent.transcript_path == "C:/tmp/a.jsonl"


# --------------------------------------------------------------------------
# adapters.py: render_output routes inject correctly for the new events.
# --------------------------------------------------------------------------


def test_context_events_and_system_message_events_match_the_live_split():
    for name in CONTEXT_NEW_EVENTS:
        assert name in _CONTEXT_EVENTS, name
    for name in SYSTEM_MESSAGE_EVENTS:
        assert name in _NO_NATIVE_CONTEXT_EVENTS, name
        assert name not in _CONTEXT_EVENTS


def test_inject_renders_additional_context_for_new_context_events():
    injected = HookResult.success(
        action="inject", additional_context=["OBSERVED: native event"]
    )
    for provider in ("claude", "codex"):
        for name in CONTEXT_NEW_EVENTS:
            rendered = render_output(injected, provider=provider, event_name=name)
            assert rendered == {
                "hookSpecificOutput": {
                    "hookEventName": name,
                    "additionalContext": "OBSERVED: native event",
                }
            }
            assert "suppressOutput" not in json.dumps(rendered)


def test_system_message_only_events_never_emit_native_additional_context():
    injected = HookResult.success(
        action="inject", additional_context=["CONFIG DRIFT detected"]
    )
    for provider in ("claude", "codex", "grok"):
        for event_name in SYSTEM_MESSAGE_EVENTS:
            rendered = render_output(injected, provider=provider, event_name=event_name)
            assert rendered == {"systemMessage": "CONFIG DRIFT detected"}


# --------------------------------------------------------------------------
# End-to-end: the dispatcher subprocess accepts every new event fail-open and
# emits only valid native JSON (mirrors the existing wire test).
# --------------------------------------------------------------------------


def test_new_native_events_have_valid_native_wire_output(tmp_path):
    script = Path(__file__).resolve().parents[1] / "dispatcher.py"
    payloads = {
        "PermissionDenied": {
            "tool_name": "Bash",
            "tool_input": {"command": "rm -rf /"},
            "permission_decision_reason": "denied by policy",
        },
        "PostToolUseFailure": {
            "tool_name": "Bash",
            "tool_use_id": "fail-1",
            "tool_input": {"command": "pytest -q"},
            "error": "exit 1",
        },
        "ConfigChange": {"path": str(tmp_path / "settings.json")},
        "TaskCreated": {"task_id": "t1", "task_type": "reviewer"},
        "TaskCompleted": {
            "task_id": "t1",
            "task_type": "reviewer",
            "summary": "SUCCESS:review",
        },
        "TeammateIdle": {"teammate_id": "m1", "teammate": "builder"},
    }
    environment = {
        **os.environ,
        "AGENT_HARNESS_STATE_ROOT": str(tmp_path / "state"),
        "BASIC_MEMORY_CHECKPOINT_DIR": str(tmp_path / "checkpoints"),
        "AGENT_HARNESS_RECALL_INDEX": str(tmp_path / "missing-index.json"),
    }
    for provider in ("claude", "codex"):
        for event_name, event_payload in payloads.items():
            payload = {
                "session_id": f"{provider}-session",
                "turn_id": "turn-1",
                "cwd": str(tmp_path),
                "permission_mode": "bypassPermissions",
                "hook_event_name": event_name,
                **event_payload,
            }
            completed = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--provider",
                    provider,
                    "--event",
                    event_name,
                    "--state-root",
                    str(tmp_path / "state"),
                ],
                input=json.dumps(payload),
                text=True,
                capture_output=True,
                timeout=10,
                env=environment,
            )
            assert completed.returncode == 0, (provider, event_name, completed.stderr)
            assert "suppressOutput" not in completed.stdout
            if completed.stdout.strip():  # pragma: no cover
                rendered = json.loads(completed.stdout)
                assert isinstance(rendered, dict)
