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
            assert command.startswith('python -X utf8 "')
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
        "Bash|PowerShell|Edit|Write|MultiEdit|NotebookEdit|apply_patch|Agent|Task"
        "|WebFetch|mcp__.*"
    )
    # Assert BEHAVIOUR, not just the string. The subagent-spawn tool was renamed
    # Task -> Agent and this matcher never followed, so every subagent spawn missed the
    # dispatcher while a subagent can do anything a session can. A string-equality
    # assertion could not catch that; these can.
    import re as _re

    _m = dispatcher_group["matcher"]
    for _gated in ("Agent", "Task", "Bash", "PowerShell", "Edit", "Write"):
        assert _re.fullmatch(_m, _gated), f"{_gated} must reach the dispatcher"
    for _ungated in ("Read", "Grep", "Glob"):
        assert not _re.fullmatch(_m, _ungated), (
            f"{_ungated} is read-only; gating it costs a dispatcher run for no gain"
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


def _run_cli(
    tmp_path, payload, *, event="PreToolUse", state="state", env=None, timeout=15
):
    """Drive the dispatcher CLI over real stdin and return (completed, terminals)."""
    script = Path(__file__).resolve().parents[1] / "dispatcher.py"
    root = tmp_path / state
    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--provider",
            "codex",
            "--event",
            event,
            "--state-root",
            str(root),
        ],
        input=payload,
        text=True,
        capture_output=True,
        timeout=timeout,
        env=env,
    )
    log = root / "terminal.jsonl"
    records = [
        json.loads(line)
        for line in (
            log.read_text(encoding="utf-8").splitlines() if log.exists() else []
        )
        if line.strip()
    ]
    return completed, records


def _run_cli_bytes(
    tmp_path, payload: bytes, *, event="PreToolUse", state="state", env=None, timeout=15
):
    script = Path(__file__).resolve().parents[1] / "dispatcher.py"
    root = tmp_path / state
    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--provider",
            "codex",
            "--event",
            event,
            "--state-root",
            str(root),
        ],
        input=payload,
        capture_output=True,
        timeout=timeout,
        env=env,
    )
    log = root / "terminal.jsonl"
    records = [
        json.loads(line)
        for line in (
            log.read_text(encoding="utf-8").splitlines() if log.exists() else []
        )
        if line.strip()
    ]
    return completed, records


def _payload_for_event(tmp_path: Path, event_name: str) -> dict[str, object]:
    payloads: dict[str, dict[str, object]] = {
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
        "PermissionDenied": {
            "tool_name": "Write",
            "tool_use_id": "deny-1",
            "tool_input": {"file_path": str(tmp_path / "x.py")},
            "permission_decision_reason": "denied by policy",
        },
        "PostToolUse": {
            "tool_name": "Write",
            "tool_use_id": "post",
            "tool_input": {"file_path": str(tmp_path / "x.py")},
            "tool_response": {"ok": True},
        },
        "PostToolUseFailure": {
            "tool_name": "Write",
            "tool_use_id": "post-fail",
            "tool_input": {"file_path": str(tmp_path / "x.py")},
            "error": "exit 1",
        },
        "PreCompact": {"trigger": "manual"},
        "PostCompact": {"trigger": "manual"},
        "ConfigChange": {"path": str(tmp_path / "settings.json")},
        "InstructionsLoaded": {"source": "startup"},
        "SubagentStart": {"agent_id": "a", "agent_type": "reviewer"},
        "SubagentStop": {
            "agent_id": "a",
            "agent_type": "reviewer",
            "last_assistant_message": "SUCCESS:review",
        },
        "TaskCreated": {"task_id": "t1", "task_type": "reviewer"},
        "TaskCompleted": {
            "task_id": "t1",
            "task_type": "reviewer",
            "summary": "SUCCESS:review",
        },
        "TeammateIdle": {"teammate_id": "m1", "teammate": "builder"},
        "Stop": {"last_assistant_message": "Work remains in progress."},
    }
    return {
        "session_id": "s",
        "turn_id": "turn-1",
        "cwd": str(tmp_path),
        "permission_mode": "bypassPermissions",
        "hook_event_name": event_name,
        **payloads[event_name],
    }


def test_cli_malformed_input_is_fail_open_and_never_emits_suppress_output(tmp_path):
    completed, records = _run_cli(tmp_path, "not-json")

    # The CLI itself still fails open at the process level, but malformed
    # PreToolUse transport must fail closed through the workspace detector.
    assert completed.returncode == 0
    assert "suppressOutput" not in completed.stdout
    if completed.stdout.strip():
        rendered = json.loads(completed.stdout)
        assert rendered["hookSpecificOutput"]["permissionDecision"] == "deny"

    assert len(records) == 1
    record = records[0]
    assert record["terminal"] == "FAILED:hook-pretooluse"
    assert record["reason_code"] == "workspace_integrity_unavailable"
    assert record["action"] == "block"
    assert record["failed_modules"] == ["_transport:malformed_json"]


def test_cli_non_object_payload_is_recorded_as_an_internal_failure(tmp_path):
    # Syntactically valid JSON that is not an object is the same fail-closed
    # transport class for PreToolUse.
    completed, records = _run_cli(tmp_path, "[1, 2, 3]")

    assert completed.returncode == 0
    assert [r["terminal"] for r in records] == ["FAILED:hook-pretooluse"]
    assert records[0]["reason_code"] == "workspace_integrity_unavailable"
    assert records[0]["action"] == "block"
    assert records[0]["failed_modules"] == ["_transport:non_object_payload"]


def test_cli_empty_stdin_for_pretooluse_is_fail_closed(tmp_path):
    completed, records = _run_cli(tmp_path, "")

    assert completed.returncode == 0
    rendered = json.loads(completed.stdout)
    assert rendered["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert [r["terminal"] for r in records] == ["FAILED:hook-pretooluse"]
    assert records[0]["reason_code"] == "workspace_integrity_unavailable"
    assert records[0]["failed_modules"] == ["_transport:empty_stdin"]


def test_cli_empty_stdin_still_records_success(tmp_path):
    # Empty stdin is normal for lifecycle events; the CLI parses it as {} and the
    # synchronous advisory path must still complete cleanly.
    completed, records = _run_cli(tmp_path, "", event="Stop")

    assert completed.returncode == 0
    assert [r["terminal"] for r in records] == ["SUCCESS:hook-stop"]
    assert records[0]["reason_code"] == "ok"
    assert records[0]["failed_modules"] == []


def test_cli_parsable_bash_payload_without_command_blocks_at_shell_gate(tmp_path):
    completed, records = _run_cli(
        tmp_path,
        '{"session_id": "s", "tool_use_id": "bash-1", "tool_name": "Bash"}',
    )

    assert completed.returncode == 0
    assert [r["terminal"] for r in records] == ["SUCCESS:hook-pretooluse"]
    assert records[0]["action"] == "block"
    assert records[0]["reason_code"] == "workspace_shell_permission"
    assert records[0]["failed_modules"] == []


def test_cli_accepts_utf8_json_bytes_with_romanian_path(tmp_path):
    payload = json.dumps(
        {
            "session_id": "s",
            "turn_id": "t",
            "cwd": "C:/Utilizatori/Prekzursil/Șură/fișier.txt",
            "hook_event_name": "Stop",
            "last_assistant_message": "Working.",
        },
        ensure_ascii=False,
    ).encode("utf-8")

    completed, records = _run_cli_bytes(tmp_path, payload, event="Stop")

    assert completed.returncode == 0
    assert completed.stdout == b"{}\n"
    assert [r["terminal"] for r in records] == ["SUCCESS:hook-stop"]


def test_cli_invalid_utf8_is_fail_closed_for_pretooluse(tmp_path):
    payload = (
        b'{"session_id":"s","turn_id":"t","cwd":"C:/x","hook_event_name":"PreToolUse",'
        b'"tool_name":"Bash","tool_use_id":"bash-1","tool_input":{"command":"pytest -q"}}'
        b"\xff"
    )

    completed, records = _run_cli_bytes(tmp_path, payload)

    assert completed.returncode == 0
    rendered = json.loads(completed.stdout.decode("utf-8"))
    assert rendered["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert [r["terminal"] for r in records] == ["FAILED:hook-pretooluse"]
    assert records[0]["failed_modules"] == ["_transport:invalid_utf8"]


def test_cli_user_prompt_submit_valid_payload_records_success(tmp_path):
    completed, records = _run_cli(
        tmp_path,
        json.dumps(
            {
                "session_id": "s",
                "turn_id": "t",
                "cwd": str(tmp_path),
                "hook_event_name": "UserPromptSubmit",
                "prompt": "Inspect the harness behavior without changing files.",
            }
        ),
        event="UserPromptSubmit",
    )

    assert completed.returncode == 0
    assert [r["terminal"] for r in records] == ["SUCCESS:hook-userpromptsubmit"]


def test_cli_subagent_stop_valid_payload_records_success(tmp_path):
    completed, records = _run_cli(
        tmp_path,
        json.dumps(
            {
                "session_id": "s",
                "turn_id": "t",
                "cwd": str(tmp_path),
                "hook_event_name": "SubagentStop",
                "agent_id": "a-1",
                "agent_type": "reviewer",
                "last_assistant_message": "SUCCESS:review",
            }
        ),
        event="SubagentStop",
    )

    assert completed.returncode == 0
    assert completed.stdout.strip() == "{}"
    assert [r["terminal"] for r in records] == ["SUCCESS:hook-subagentstop"]


def test_dispatch_transport_error_is_named_in_the_terminal_record(tmp_path):
    # Unit-level twin of the CLI tests: the classification lives in dispatch(),
    # so it is available to any embedder, not only the argv entrypoint.
    dispatcher = HarnessDispatcher(modules=[], state_root=tmp_path / "state")
    result = dispatcher.dispatch(
        {},
        provider="codex",
        event_name="Stop",
        transport_error="_transport:malformed_json",
    )

    assert result.action == "allow"
    assert result.status == "FAILED:hook-stop"
    assert result.reason_code == "internal_error"
    assert result.additional_context == []


def test_cli_top_level_exception_for_pretooluse_emits_fail_closed_block(tmp_path):
    agent_self = str(Path(__file__).resolve().parents[2])
    patch_dir = tmp_path / "patches"
    patch_dir.mkdir()
    sitecustomize = patch_dir / "sitecustomize.py"
    sitecustomize.write_text(
        "import sys\n"
        f"sys.path.insert(0, {agent_self!r})\n"
        "import harness.modules as m\n"
        "def _boom(*args, **kwargs):\n"
        "    raise RuntimeError('boom')\n"
        "m.build_default_modules = _boom\n",
        encoding="utf-8",
    )
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join([str(patch_dir), agent_self]),
    }

    completed, records = _run_cli(
        tmp_path,
        json.dumps(
            {
                "session_id": "s",
                "turn_id": "t",
                "cwd": str(tmp_path),
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "tool_use_id": "bash-1",
                "tool_input": {"command": "pytest -q"},
            }
        ),
        env=env,
    )

    assert completed.returncode == 0
    rendered = json.loads(completed.stdout)
    assert rendered["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert [r["terminal"] for r in records] == ["FAILED:hook-pretooluse"]
    assert records[0]["failed_modules"] == ["_cli:exception"]


def test_cli_top_level_exception_for_stop_is_failed_open(tmp_path):
    agent_self = str(Path(__file__).resolve().parents[2])
    patch_dir = tmp_path / "patches"
    patch_dir.mkdir()
    sitecustomize = patch_dir / "sitecustomize.py"
    sitecustomize.write_text(
        "import sys\n"
        f"sys.path.insert(0, {agent_self!r})\n"
        "import harness.modules as m\n"
        "def _boom(*args, **kwargs):\n"
        "    raise RuntimeError('boom')\n"
        "m.build_default_modules = _boom\n",
        encoding="utf-8",
    )
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join([str(patch_dir), agent_self]),
    }

    completed, records = _run_cli(
        tmp_path,
        json.dumps(
            {
                "session_id": "s",
                "turn_id": "t",
                "cwd": str(tmp_path),
                "hook_event_name": "Stop",
                "last_assistant_message": "Working.",
            }
        ),
        event="Stop",
        env=env,
    )

    assert completed.returncode == 0
    assert completed.stdout.strip() == "{}"
    assert [r["terminal"] for r in records] == ["FAILED:hook-stop"]
    assert records[0]["action"] == "allow"
    assert records[0]["reason_code"] == "internal_error"
    assert records[0]["failed_modules"] == ["_cli:exception"]


@pytest.mark.parametrize("event_name", EVENTS)
def test_cli_top_level_exception_emits_nonempty_json_for_every_event(
    tmp_path, event_name: str
):
    agent_self = str(Path(__file__).resolve().parents[2])
    patch_dir = tmp_path / f"patches-{event_name}"
    patch_dir.mkdir()
    sitecustomize = patch_dir / "sitecustomize.py"
    sitecustomize.write_text(
        "import sys\n"
        f"sys.path.insert(0, {agent_self!r})\n"
        "import harness.modules as m\n"
        "def _boom(*args, **kwargs):\n"
        "    raise RuntimeError('boom')\n"
        "m.build_default_modules = _boom\n",
        encoding="utf-8",
    )
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join([str(patch_dir), agent_self]),
    }

    completed, records = _run_cli(
        tmp_path,
        json.dumps(_payload_for_event(tmp_path, event_name)),
        event=event_name,
        env=env,
    )

    assert completed.returncode == 0
    assert completed.stdout.strip()
    rendered = json.loads(completed.stdout)
    assert isinstance(rendered, dict)
    if event_name == "PreToolUse":
        assert rendered["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert [r["terminal"] for r in records] == [f"FAILED:hook-{event_name.lower()}"]
    assert records[0]["failed_modules"] == ["_cli:exception"]


def test_cli_known_stall_remains_bound_by_host_process_timeout(tmp_path):
    agent_self = str(Path(__file__).resolve().parents[2])
    patch_dir = tmp_path / "patches"
    patch_dir.mkdir()
    sitecustomize = patch_dir / "sitecustomize.py"
    sitecustomize.write_text(
        "import sys, time\n"
        f"sys.path.insert(0, {agent_self!r})\n"
        "import harness.modules as m\n"
        "from harness.models import HookResult\n"
        "class _Stall:\n"
        "    name = 'stall'\n"
        "    def run(self, _event):\n"
        "        time.sleep(10)\n"
        "        return HookResult.success()\n"
        "m.build_default_modules = lambda state_root: [_Stall()]\n",
        encoding="utf-8",
    )
    script = Path(__file__).resolve().parents[1] / "dispatcher.py"
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join([str(patch_dir), agent_self]),
    }

    with pytest.raises(subprocess.TimeoutExpired):
        subprocess.run(
            [
                sys.executable,
                str(script),
                "--provider",
                "codex",
                "--event",
                "Stop",
                "--state-root",
                str(tmp_path / "state"),
            ],
            input=json.dumps({"cwd": str(tmp_path), "hook_event_name": "Stop"}),
            text=True,
            capture_output=True,
            timeout=0.3,
            env=env,
        )


def test_every_registered_provider_event_has_valid_native_wire_output(tmp_path):
    script = Path(__file__).resolve().parents[1] / "dispatcher.py"
    environment = {
        **os.environ,
        "AGENT_HARNESS_STATE_ROOT": str(tmp_path / "state"),
        "BASIC_MEMORY_CHECKPOINT_DIR": str(tmp_path / "checkpoints"),
        "AGENT_HARNESS_RECALL_INDEX": str(tmp_path / "missing-index.json"),
    }
    for provider in ("claude", "codex"):
        for event_name in EVENTS:
            payload = _payload_for_event(tmp_path, event_name)
            payload["session_id"] = f"{provider}-session"
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
