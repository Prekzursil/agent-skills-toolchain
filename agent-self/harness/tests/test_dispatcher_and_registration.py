from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from harness.dispatcher import HarnessDispatcher
from harness.models import HookResult
from harness.registration import EVENTS, build_hooks
from harness import registration as _registration

# The dispatcher path build_hooks embeds is derived from registration.py's own
# location (Path(__file__).resolve().parent / "dispatcher.py"), so it is
# ".agents/harness/dispatcher.py" in the LIVE install but ".../ci/harness/
# dispatcher.py" in this enshrined layout. Compute the expected path the same way
# so the assertions target the harness's OWN dispatcher wherever it lives, rather
# than hard-coding the live install path (which fails in the enshrined tree).
_DISPATCHER = (
    Path(_registration.__file__).resolve().parent / "dispatcher.py"
).as_posix()


class ExplodingModule:
    name = "exploder"

    def run(self, _event):
        raise RuntimeError("sensitive internal detail")


def test_dispatcher_fails_open_and_records_terminal_failure(tmp_path):
    dispatcher = HarnessDispatcher(
        modules=[ExplodingModule()], state_root=tmp_path / "state"
    )

    result = dispatcher.dispatch(
        {
            "session_id": "s",
            "cwd": str(tmp_path),
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "pytest -q"},
        },
        provider="codex",
        event_name="PreToolUse",
    )

    assert result.action == "allow"
    assert result.status.startswith("FAILED:")
    assert result.reason_code == "internal_error"
    assert "sensitive internal detail" not in " ".join(result.additional_context)
    log = (tmp_path / "state" / "terminal.jsonl").read_text(encoding="utf-8")
    assert "FAILED:hook-pretooluse" in log


def test_dispatcher_aggregates_context_and_block_wins(tmp_path):
    class ContextModule:
        name = "context"

        def run(self, _event):
            return HookResult.success(
                action="inject", additional_context=["context one"]
            )

    class BlockModule:
        name = "block"

        def run(self, _event):
            return HookResult.success(
                action="block",
                reason_code="secret_literal",
                additional_context=["Blocked safely."],
            )

    dispatcher = HarnessDispatcher(
        modules=[ContextModule(), BlockModule()], state_root=tmp_path / "state"
    )
    result = dispatcher.dispatch(
        {
            "session_id": "s",
            "cwd": str(tmp_path),
            "tool_name": "Bash",
            "tool_input": {"command": "echo safe"},
        },
        provider="claude",
        event_name="PreToolUse",
    )

    assert result.action == "block"
    assert result.additional_context == ["context one", "Blocked safely."]


def test_dispatcher_stops_after_block_before_persistence_capable_modules(tmp_path):
    calls = []

    class BlockModule:
        name = "secret_guard"

        def run(self, _event):
            calls.append("block")
            return HookResult.success(
                action="block",
                reason_code="secret_literal",
                additional_context=["Blocked."],
            )

    class PersistenceModule:
        name = "event_ledger"

        def run(self, _event):  # pragma: no cover
            calls.append("persist")
            return HookResult.success()

    dispatcher = HarnessDispatcher(
        modules=[BlockModule(), PersistenceModule()], state_root=tmp_path / "state"
    )
    result = dispatcher.dispatch(
        {
            "session_id": "s",
            "cwd": str(tmp_path),
            "tool_name": "Bash",
            "tool_input": {"command": "echo safe"},
        },
        provider="codex",
        event_name="PreToolUse",
    )

    assert result.action == "block"
    assert calls == ["block"]


def test_registration_has_exactly_one_dispatcher_per_supported_event():
    # Updated for FIX 3: build_hooks("claude") now folds in the live settings.json
    # hand-edits (a 2nd SessionStart/PreToolUse group + WorktreeCreate/Remove), so
    # "one group per event" no longer holds for claude. The load-bearing invariant
    # that survives is: every SUPPORTED (EVENTS) event carries EXACTLY ONE
    # dispatcher group, correctly targeted. codex stays strictly minimal.
    marker = _DISPATCHER
    for provider in ("claude", "codex"):
        hooks = build_hooks(provider)
        for event_name in EVENTS:
            assert event_name in hooks
            dispatcher_groups = [
                group
                for group in hooks[event_name]
                if marker in group["hooks"][0]["command"].replace("\\", "/")
            ]
            assert len(dispatcher_groups) == 1
            command = dispatcher_groups[0]["hooks"][0]["command"]
            assert f"--provider {provider}" in command
            assert f"--event {event_name}" in command
            assert "precompact-basicmemory" not in command
    # codex carries no hand-edits: exactly the EVENTS keys, one group each.
    codex = build_hooks("codex")
    assert tuple(codex) == EVENTS
    for groups in codex.values():
        assert len(groups) == 1
        assert len(groups[0]["hooks"]) == 1


def test_claude_build_hooks_folds_in_live_settings_hand_edits():
    # FIX 3 regression lock: the five Claude-only hand-edits present in the live
    # ~/.claude/settings.json must be regenerated verbatim by build_hooks("claude")
    # so `install.py --check` stays drift-free and a regenerated block never wipes
    # them. None of these leak into the codex block.
    claude = build_hooks("claude")
    codex = build_hooks("codex")

    # (a) PreToolUse dispatcher matcher is hand-narrowed for claude, broad for codex.
    pre = claude["PreToolUse"]
    dispatcher_group = next(
        g for g in pre if "dispatcher.py" in g["hooks"][0]["command"]
    )
    assert dispatcher_group["matcher"] == (
        "Bash|PowerShell|Edit|Write|MultiEdit|NotebookEdit|apply_patch|Task|WebFetch|mcp__.*"
    )
    assert codex["PreToolUse"][0]["matcher"] == ".*"

    # (b) 2nd SessionStart group: the local-TUI reminder.
    assert len(claude["SessionStart"]) == 2
    assert claude["SessionStart"][1]["matcher"] == ".*"
    tui = claude["SessionStart"][1]["hooks"][0]
    assert tui["command"].endswith('local-tui-reminder/check.py"')
    assert (tui["timeout"], tui["statusMessage"]) == (5, "local-TUI reminder")

    # (c) 2nd PreToolUse group: wfmon auto-launch, matcher "Workflow".
    workflow = next(g for g in pre if g.get("matcher") == "Workflow")
    wf = workflow["hooks"][0]
    assert wf["command"].endswith('workflow-monitor-autolaunch/check.py"')
    assert (wf["timeout"], wf["statusMessage"]) == (8, "wfmon auto-launch")

    # (d)/(e) WorktreeCreate + WorktreeRemove: PowerShell scripts, no matcher,
    # claude-only.
    for event_name, script, timeout, status in (
        ("WorktreeCreate", "create-worktree.ps1", 60, "Creating git worktree"),
        ("WorktreeRemove", "remove-worktree.ps1", 30, "Removing git worktree"),
    ):
        assert event_name in claude and event_name not in codex
        group = claude[event_name][0]
        assert "matcher" not in group
        hook = group["hooks"][0]
        assert hook["command"].lower().startswith("powershell -noprofile")
        assert hook["command"].endswith(f'{script}"')
        assert (hook["timeout"], hook["statusMessage"]) == (timeout, status)


def test_cli_malformed_input_is_fail_open_and_never_emits_suppress_output(tmp_path):
    script = Path(__file__).resolve().parents[1] / "dispatcher.py"
    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--provider",
            "codex",
            "--event",
            "PreToolUse",
            "--state-root",
            str(tmp_path / "state"),
        ],
        input="not-json",
        text=True,
        capture_output=True,
        timeout=5,
    )

    assert completed.returncode == 0
    assert "suppressOutput" not in completed.stdout
    if completed.stdout.strip():  # pragma: no cover
        json.loads(completed.stdout)


def test_every_registered_provider_event_has_valid_native_wire_output(tmp_path):
    script = Path(__file__).resolve().parents[1] / "dispatcher.py"
    payloads = {
        "SessionStart": {"source": "startup"},
        "UserPromptSubmit": {
            "prompt": "Inspect the shared harness behavior without changing files."
        },
        "PreToolUse": {
            "tool_name": "Bash",
            "tool_use_id": "pre",
            "tool_input": {"command": "pytest -q"},
        },
        "PermissionRequest": {
            "tool_name": "Bash",
            "tool_input": {"command": "pytest -q"},
        },
        "PostToolUse": {
            "tool_name": "Bash",
            "tool_use_id": "post",
            "tool_input": {"command": "pytest -q"},
            "tool_response": {"exit_code": 0, "output": "1 passed"},
        },
        "PreCompact": {"trigger": "manual"},
        "PostCompact": {"trigger": "manual"},
        "SubagentStart": {"agent_id": "a", "agent_type": "reviewer"},
        "SubagentStop": {
            "agent_id": "a",
            "agent_type": "reviewer",
            "last_assistant_message": "SUCCESS:review",
        },
        "Stop": {"last_assistant_message": "Work remains in progress."},
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
                timeout=5,
                env=environment,
            )
            assert completed.returncode == 0, (provider, event_name, completed.stderr)
            assert "suppressOutput" not in completed.stdout
            if completed.stdout.strip():
                rendered = json.loads(completed.stdout)
                assert isinstance(rendered, dict)


def test_legacy_basic_memory_capture_is_a_safe_shared_dispatcher_wrapper():
    legacy_hook = (
        Path.home() / ".claude" / "hooks" / "precompact-basicmemory" / "capture.ps1"
    )
    if not legacy_hook.exists():  # pragma: no cover - hook only present once deployed
        pytest.skip("legacy basic-memory capture hook is not deployed in this env")
    legacy = legacy_hook.read_text(encoding="utf-8")

    assert ".agents/harness/dispatcher.py" in legacy.replace("\\", "/")
    assert "--provider claude --event PreCompact" in legacy
    assert "transcript_path" not in legacy
    assert "Recent user intent" not in legacy
    assert "suppressOutput" not in legacy
