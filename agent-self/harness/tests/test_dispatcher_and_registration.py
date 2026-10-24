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

    # (c) REMOVED 2026-10-24. This used to assert a standalone "Workflow"-matcher
    # group running workflow-monitor-autolaunch. Asserting its ABSENCE instead of
    # just deleting the check, so re-adding it fails loudly: the dispatcher already
    # admits Workflow and runs the generalized monitor-autolaunch on
    # Task|Workflow|mcp__codex__codex, and the two groups' per-session locks have
    # different names, so neither suppresses the other. Measured consequence per
    # CLOSE-PROPOSALS-M1.md:25 is two tabs and two poller processes in one reusable
    # window (both launch `wt -w <name> new-tab`), not two windows.
    assert not [g for g in pre if g.get("matcher") == "Workflow"], (
        "no standalone Workflow group may be generated: the dispatcher owns that "
        "route, and a second launcher guarantees a duplicate window"
    )
    assert "workflow-monitor-autolaunch" not in json.dumps(claude), (
        "the superseded legacy hook must not be wired anywhere in the built block"
    )

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


def test_grok_build_hooks_keeps_broad_matcher_and_no_claude_hand_edits():
    # Pins the two DELIBERATE branch decisions taken when grok was accepted by
    # build_hooks on the live tree (2026-08-08; ported in the 2026-09-02 reunion).
    # Both are safety decisions, so they get a test rather than only a comment.
    grok = build_hooks("grok")
    claude = build_hooks("claude")
    codex = build_hooks("codex")

    # (1) grok must NOT inherit the claude-narrowed PreToolUse matcher. That
    # constant enumerates CLAUDE tool names; measured against the shipped
    # grok.exe it matches 1 of 13 real Grok tool names and misses Grok's shell
    # tool entirely, so narrowing grok would make the destructive-command guard
    # blind to every Grok shell command.
    import re as _re

    grok_pre = next(
        g for g in grok["PreToolUse"] if "dispatcher.py" in g["hooks"][0]["command"]
    )
    claude_pre = next(
        g for g in claude["PreToolUse"] if "dispatcher.py" in g["hooks"][0]["command"]
    )
    assert grok_pre["matcher"] == ".*"
    assert grok_pre["matcher"] != claude_pre["matcher"]
    for grok_tool in ("run_terminal_command", "search_replace", "write_file"):
        assert _re.fullmatch(grok_pre["matcher"], grok_tool), (
            f"{grok_tool} must reach the dispatcher on grok"
        )
        assert not _re.fullmatch(claude_pre["matcher"], grok_tool), (
            f"{grok_tool} is missed by the claude matcher -- that is WHY grok "
            f"keeps '.*'; if this now matches, re-derive the decision"
        )

    # (2) grok gets none of the claude-only hand-edits: the worktree events do
    # not exist on grok, and the other two point at ~/.claude/hooks tooling.
    assert tuple(grok) == EVENTS
    assert "WorktreeCreate" not in grok and "WorktreeRemove" not in grok
    for groups in grok.values():
        assert len(groups) == 1
        assert len(groups[0]["hooks"]) == 1
    assert tuple(grok) == tuple(codex)

    # (3) the generated command still carries the right provider.
    for event_name in EVENTS:
        assert "--provider grok" in grok[event_name][0]["hooks"][0]["command"]


def _run_cli(tmp_path, payload, *, event="PreToolUse", state="state", provider="codex"):
    """Drive the dispatcher CLI over real stdin and return (completed, terminals)."""
    script = Path(__file__).resolve().parents[1] / "dispatcher.py"
    root = tmp_path / state
    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--provider",
            provider,
            "--event",
            event,
            "--state-root",
            str(root),
        ],
        input=payload,
        text=True,
        capture_output=True,
        timeout=15,
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


def test_cli_malformed_input_is_fail_open_and_never_emits_suppress_output(tmp_path):
    completed, records = _run_cli(tmp_path, "not-json")

    # Fail-open on the wire is deliberate: the host must never be blocked or
    # crashed by a payload the harness could not parse.
    assert completed.returncode == 0
    assert "suppressOutput" not in completed.stdout
    if completed.stdout.strip():  # pragma: no cover
        json.loads(completed.stdout)

    # D010 · but exit 0 alone must NOT pass. The durable record has to say the
    # invocation failed internally, otherwise a promotion/smoke oracle grades a
    # silently-lost hook invocation as green.
    assert len(records) == 1
    record = records[0]
    assert record["terminal"] == "FAILED:hook-pretooluse"
    assert record["reason_code"] == "internal_error"
    assert record["action"] == "allow"
    assert record["failed_modules"] == ["_transport:malformed_json"]


def test_cli_non_object_payload_is_recorded_as_an_internal_failure(tmp_path):
    # Syntactically valid JSON that is not an object is the same class of wire
    # failure: the modules run over {} and observe nothing the host sent.
    completed, records = _run_cli(tmp_path, "[1, 2, 3]")

    assert completed.returncode == 0
    assert [r["terminal"] for r in records] == ["FAILED:hook-pretooluse"]
    assert records[0]["failed_modules"] == ["_transport:non_object_payload"]


@pytest.mark.parametrize("payload", ["", '{"tool_name": "Bash"}'])
def test_cli_parsable_payload_still_records_success(tmp_path, payload):
    # KNOWN-NEGATIVE control for the two assertions above: empty stdin is normal
    # for several hosts and a well-formed object is the happy path, so neither
    # may be demoted to FAILED by the transport guard.
    completed, records = _run_cli(tmp_path, payload)

    assert completed.returncode == 0
    assert [r["terminal"] for r in records] == ["SUCCESS:hook-pretooluse"]
    assert records[0]["reason_code"] == "ok"
    assert records[0]["failed_modules"] == []


def test_cli_accepts_grok_and_attributes_the_terminal_record_to_it(tmp_path):
    # The argparse `choices` gate and adapters.SUPPORTED_PROVIDERS must move
    # together (see test_contract): before the live fix, `--provider grok` was
    # rejected by argparse (rc 2) and Grok's hooks ran as `--provider claude`, so
    # every Grok turn was attributed to claude. One real process, end to end.
    completed, records = _run_cli(
        tmp_path, '{"session_id": "g", "tool_name": "Bash"}', provider="grok"
    )

    assert completed.returncode == 0
    assert "suppressOutput" not in completed.stdout
    assert [r["terminal"] for r in records] == ["SUCCESS:hook-pretooluse"]
    assert records[0]["provider"] == "grok"


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


def test_every_registered_provider_event_has_valid_native_wire_output(tmp_path):
    """KNOWN INTERMITTENT FAILURE under load, measured 2026-08-11. Not yet root-caused.

    It spawns ``dispatcher.py`` as a SUBPROCESS once per event type -- 11 processes, ~27s alone --
    which makes it the most timing-sensitive test in this suite.

        isolated          5 runs, 5 passes
        in the full suite 2 of 6 runs failed (~33%; two later capture attempts both passed, which
                          is why the assertion text is still unrecorded)
        failure count     varies between runs (2 once, 1 another) -- nondeterministic
        timing            BOTH failing runs were the SLOWEST of their batch (368s, 357s) against
                          184s / 157s / 143s for passing ones

    So the signature is contention, not logic and not test ORDER: both failures happened while other
    suites and `gh` pollers were running concurrently on the same box. CI installs no ordering
    plugin, runs one suite at a time on a dedicated runner, and is green (835/835).

    If you see this red locally, re-run it alone before believing it. If you see it red in CI, that
    IS new information -- say so, because it has not happened yet.
    """
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
