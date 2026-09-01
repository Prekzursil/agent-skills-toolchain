from __future__ import annotations

import dataclasses
import json
import os
import subprocess
import sys
from pathlib import Path

from harness.adapters import _CONTEXT_EVENTS, normalize_event, render_output
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

# The subset that renders inject as native additionalContext. Only
# PostToolUseFailure qualifies: it is the one new name with an
# additionalContext-bearing member in the host's hookSpecificOutput output
# union. See NO_CONTEXT_NEW_EVENTS for the rest.
CONTEXT_NEW_EVENTS = ("PostToolUseFailure",)

# Events that FIRE but whose inject MUST render as systemMessage, because the
# host's hookSpecificOutput union either has no member for them at all
# (PostCompact/TaskCompleted/TaskCreated/TeammateIdle -> validation failure ->
# the whole hook payload is discarded as plainText) or has a member that does
# not carry additionalContext (PermissionDenied -> {hookEventName, retry?} ->
# the key is silently stripped). ConfigChange was already a systemMessage.
NO_CONTEXT_NEW_EVENTS = (
    "PostCompact",
    "TaskCompleted",
    "TaskCreated",
    "TeammateIdle",
    "PermissionDenied",
    "ConfigChange",
)

# Replica of the claude hookSpecificOutput output union, keyed by the
# `hookEventName` literal -> the set of sibling keys that member accepts.
# Transcribed 2026-07-27 from the installed claude 2.1.220 binary (the
# `HuE()` object's `hookSpecificOutput: v.union([...])`). Anything not a key
# here has NO union member, so the host rejects the whole payload.
HOST_HOOK_SPECIFIC_OUTPUT_UNION: dict[str, set[str]] = {
    "PreToolUse": {
        "permissionDecision",
        "permissionDecisionReason",
        "updatedInput",
        "additionalContext",
    },
    "UserPromptSubmit": {
        "additionalContext",
        "sessionTitle",
        "suppressOriginalPrompt",
    },
    "UserPromptExpansion": {"additionalContext"},
    "SessionStart": {
        "additionalContext",
        "initialUserMessage",
        "sessionTitle",
        "watchPaths",
        "reloadSkills",
    },
    "Setup": {"additionalContext"},
    "SubagentStart": {"additionalContext"},
    "PostToolUse": {
        "additionalContext",
        "updatedToolOutput",
        "updatedMCPToolOutput",
    },
    "PostToolUseFailure": {"additionalContext"},
    "PostToolBatch": {"additionalContext"},
    "Stop": {"additionalContext"},
    "SubagentStop": {"additionalContext"},
    "PermissionDenied": {"retry"},
    "Notification": {"additionalContext"},
    "PermissionRequest": {"decision"},
    "Elicitation": {"action", "content"},
    "ElicitationResult": {"action", "content"},
    "CwdChanged": {"watchPaths"},
    "FileChanged": {"watchPaths"},
    "WorktreeCreate": {"worktreePath"},
    "MessageDisplay": {"displayContent"},
}


def assert_host_accepts(rendered: dict, event_name: str) -> None:
    """Fail if the host would reject or silently strip this hook output.

    Mirrors claude's `_ip()`: the payload is validated against the
    hookSpecificOutput union, and a miss makes `K2o()` return a
    validationError so the ENTIRE output degrades to plainText.
    """
    block = rendered.get("hookSpecificOutput")
    if block is None:
        return
    name = block.get("hookEventName")
    assert name is not None, f"{event_name}: hookSpecificOutput without hookEventName"
    assert name in HOST_HOOK_SPECIFIC_OUTPUT_UNION, (
        f"{event_name}: hookEventName={name!r} matches NO member of the host's "
        "hookSpecificOutput union -> validationError -> the whole hook output "
        "is discarded as plainText"
    )
    allowed = HOST_HOOK_SPECIFIC_OUTPUT_UNION[name]
    extra = set(block) - {"hookEventName"} - allowed
    assert not extra, (
        f"{event_name}: hookSpecificOutput carries {sorted(extra)}, which the "
        f"{name} member does not accept (allowed: {sorted(allowed)}) -> the "
        "host strips it and the context never reaches the model"
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
    # reviewed change - the module reads the transcript it is asked to classify.
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


def test_context_events_only_holds_names_the_host_union_accepts():
    for name in CONTEXT_NEW_EVENTS:
        assert name in _CONTEXT_EVENTS, name
    # Every context event must have an additionalContext-bearing union member.
    for name in _CONTEXT_EVENTS:
        assert "additionalContext" in HOST_HOOK_SPECIFIC_OUTPUT_UNION.get(
            name, set()
        ), (
            f"{name} is in _CONTEXT_EVENTS but the host union cannot carry "
            "additionalContext for it"
        )
    for name in NO_CONTEXT_NEW_EVENTS:
        assert name not in _CONTEXT_EVENTS, name


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
            assert_host_accepts(rendered, name)


def test_inject_never_emits_hook_specific_output_the_host_would_discard():
    # REGRESSION (wu-06 F1): PostCompact/TaskCompleted/TaskCreated/TeammateIdle
    # have NO member in the host's hookSpecificOutput union, and
    # PermissionDenied's member is {hookEventName, retry?} only. Emitting
    # additionalContext for any of them loses the injected context — for the
    # first four it also discards the ENTIRE hook output as plainText.
    injected = HookResult.success(
        action="inject", additional_context=["OBSERVED: native event"]
    )
    for provider in ("claude", "codex"):
        for name in NO_CONTEXT_NEW_EVENTS:
            rendered = render_output(injected, provider=provider, event_name=name)
            assert_host_accepts(rendered, name)
            assert rendered == {"systemMessage": "OBSERVED: native event"}, (
                f"{name}/{provider} rendered {rendered!r}"
            )


def test_every_rendered_hook_specific_output_survives_the_host_union():
    # Blanket guard across every event the harness registers, for both actions
    # that can emit hookSpecificOutput.
    for action, kwargs in (
        ("inject", {"additional_context": ["ctx"]}),
        ("block", {"reason_code": "policy_block"}),
    ):
        result = HookResult.success(action=action, **kwargs)
        for provider in ("claude", "codex"):
            for name in EVENTS:
                assert_host_accepts(
                    render_output(result, provider=provider, event_name=name), name
                )


def test_config_change_inject_renders_as_system_message():
    injected = HookResult.success(
        action="inject", additional_context=["CONFIG DRIFT detected"]
    )
    rendered = render_output(injected, provider="claude", event_name="ConfigChange")
    assert rendered == {"systemMessage": "CONFIG DRIFT detected"}


# --------------------------------------------------------------------------
# adapters.py: turn identity (wu-06 F2/F6).
# --------------------------------------------------------------------------


def test_turn_id_falls_back_to_the_hosts_prompt_id():
    # REGRESSION (wu-06 F2/F6): the claude base hook payload has no turn_id —
    # it names the turn `prompt_id`. Reading turn_id alone left turn_id "" on
    # every claude event, and an empty turn DISABLES the turn filter in
    # ledger._receipts / _has_legacy_verification / last_mutation_seq. Measured
    # 2026-07-27 on the live ledger: 112076/112076 claude tool_result records
    # had turn_id == "" vs 16970/16971 populated for codex.
    event = normalize_event(
        {
            "session_id": "s1",
            "transcript_path": "C:/tmp/t.jsonl",
            "cwd": "C:/repo",
            "prompt_id": "prompt-abc",
            "permission_mode": "default",
        },
        provider="claude",
        event_name="PostToolUse",
    )
    assert event.turn_id == "prompt-abc"


def test_explicit_turn_id_still_beats_prompt_id():
    event = normalize_event(
        {"turn_id": "turn-1", "prompt_id": "prompt-abc"},
        provider="codex",
        event_name="PostToolUse",
    )
    assert event.turn_id == "turn-1"


def test_turn_id_stays_empty_when_neither_key_is_present():
    event = normalize_event({}, provider="claude", event_name="PostToolUse")
    assert event.turn_id == ""


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
