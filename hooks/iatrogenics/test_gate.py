#!/usr/bin/env python3
"""pytest tests for iatrogenics/gate.py.

Run:  pytest test_gate.py -v
      python -m pytest test_gate.py -v

Covers:
  - no-trigger (reversible actions → silent)
  - MCP tool triggers fire on first occurrence
  - Bash command triggers: SILENT on occurrence #1 (watchful-waiting premise requires
    recurrence), fire from occurrence #2 onwards
  - counter mechanics (silences after K)
  - calibrated-silence gate: suppresses when ledger indicates noise; fail-open when disabled
  - fail-open (bad stdin)
  - opt-out (env + .disabled)
  - L4 size cap (huge command does not hang/crash)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
HOOK = str(HERE / "gate.py")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run_hook(payload: dict, env_extra: dict | None = None, timeout: int = 15) -> tuple[int, str, str]:
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    p = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
    )
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def fired(stdout: str) -> bool:
    if not stdout:
        return False
    try:
        return bool(
            json.loads(stdout)
            .get("hookSpecificOutput", {})
            .get("additionalContext", "")
        )
    except Exception:
        return False


def ctx_of(stdout: str) -> str:
    try:
        return json.loads(stdout)["hookSpecificOutput"]["additionalContext"]
    except Exception:
        return ""


def _make_suppressing_ledger(path: Path, itype: str, count: int = 10) -> None:
    """Write enough 'ignored' rows to force calibrated-silence to suppress.

    Wilson center with 0 acted / 10 ignored ≈ 0.14; value(suggestion)=0.9 → ev≈0.13
    which is below the default BASE_THRESHOLD of 0.40, so should_interject returns False.
    """
    rows = []
    base_ts = time.time() - count * 120  # space them 2 min apart
    for i in range(count):
        rows.append(json.dumps({
            "ts": base_ts + i * 120,
            "type": itype,
            "context_key": f"test_{i}",
            "session_id": "ledger-test",
            "surfaced": True,
            "reaction": "ignored",
        }))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# No-trigger: reversible actions
# ---------------------------------------------------------------------------

class TestNoTrigger:
    def test_reversible_bash_ls(self, tmp_path):
        """Plain 'ls -la' — reversible, no inject."""
        env = {"IATROGENICS_COUNTER_DIR": str(tmp_path)}
        rc, out, _ = run_hook(
            {"tool_name": "Bash", "tool_input": {"command": "ls -la"},
             "session_id": "rev-ls"},
            env_extra=env,
        )
        assert rc == 0
        assert not fired(out)

    def test_reversible_bash_git_status(self, tmp_path):
        """'git status' — read-only, no inject."""
        env = {"IATROGENICS_COUNTER_DIR": str(tmp_path)}
        rc, out, _ = run_hook(
            {"tool_name": "Bash", "tool_input": {"command": "git status"},
             "session_id": "rev-git"},
            env_extra=env,
        )
        assert rc == 0
        assert not fired(out)

    def test_reversible_bash_rm_no_flags(self, tmp_path):
        """'rm somefile' without -f / -r — not matched by irreversible heuristic."""
        env = {"IATROGENICS_COUNTER_DIR": str(tmp_path)}
        rc, out, _ = run_hook(
            {"tool_name": "Bash", "tool_input": {"command": "rm somefile.txt"},
             "session_id": "rev-rm"},
            env_extra=env,
        )
        assert rc == 0
        assert not fired(out)

    def test_reversible_edit_normal_file(self, tmp_path):
        """Edit to a normal source file — reversible (git-tracked), no inject."""
        env = {"IATROGENICS_COUNTER_DIR": str(tmp_path)}
        rc, out, _ = run_hook(
            {"tool_name": "Edit",
             "tool_input": {"file_path": "/home/user/project/src/main.py",
                            "old_string": "x = 1", "new_string": "x = 2"},
             "session_id": "rev-edit"},
            env_extra=env,
        )
        assert rc == 0
        assert not fired(out)

    def test_frida_safe_enumerate(self, tmp_path):
        """mcp__frida-mcp__enumerate_processes — read-only, no inject."""
        env = {"IATROGENICS_COUNTER_DIR": str(tmp_path)}
        rc, out, _ = run_hook(
            {"tool_name": "mcp__frida-mcp__enumerate_processes",
             "tool_input": {},
             "session_id": "rev-frida"},
            env_extra=env,
        )
        assert rc == 0
        assert not fired(out)


# ---------------------------------------------------------------------------
# MCP tool triggers: fire on first occurrence (no first-occurrence skip)
# ---------------------------------------------------------------------------

class TestMcpToolTrigger:
    def test_cheatengine_write_integer_first_occurrence(self, tmp_path):
        """mcp__cheatengine__write_integer fires on occurrence #1 (MCP → immediate advisory)."""
        env = {"IATROGENICS_COUNTER_DIR": str(tmp_path), "CALIBRATED_SILENCE": "off"}
        rc, out, _ = run_hook(
            {"tool_name": "mcp__cheatengine__write_integer",
             "tool_input": {"address": "0x12345678", "value": 9999, "type": "4bytes"},
             "session_id": "irr-ce1"},
            env_extra=env,
        )
        assert rc == 0
        assert fired(out)
        ctx = ctx_of(out)
        assert "IATROGENICS" in ctx or "watchful-waiting" in ctx.lower()

    def test_cheatengine_auto_assemble_first_occurrence(self, tmp_path):
        """mcp__cheatengine__auto_assemble fires on first occurrence."""
        env = {"IATROGENICS_COUNTER_DIR": str(tmp_path), "CALIBRATED_SILENCE": "off"}
        rc, out, _ = run_hook(
            {"tool_name": "mcp__cheatengine__auto_assemble",
             "tool_input": {"script": "mov [rax],1"},
             "session_id": "irr-ce2"},
            env_extra=env,
        )
        assert rc == 0
        assert fired(out)

    def test_frida_execute_in_session_first_occurrence(self, tmp_path):
        """mcp__frida-mcp__execute_in_session fires on first occurrence."""
        env = {"IATROGENICS_COUNTER_DIR": str(tmp_path), "CALIBRATED_SILENCE": "off"}
        rc, out, _ = run_hook(
            {"tool_name": "mcp__frida-mcp__execute_in_session",
             "tool_input": {"session_id": "s1",
                            "script": "Memory.writeU8(ptr('0x1000'), 0)"},
             "session_id": "irr-frida"},
            env_extra=env,
        )
        assert rc == 0
        assert fired(out)

    def test_frida_spawn_process_first_occurrence(self, tmp_path):
        """mcp__frida-mcp__spawn_process fires on first occurrence."""
        env = {"IATROGENICS_COUNTER_DIR": str(tmp_path), "CALIBRATED_SILENCE": "off"}
        rc, out, _ = run_hook(
            {"tool_name": "mcp__frida-mcp__spawn_process",
             "tool_input": {"program": "/usr/bin/target"},
             "session_id": "irr-spawn"},
            env_extra=env,
        )
        assert rc == 0
        assert fired(out)


# ---------------------------------------------------------------------------
# Bash command triggers: SILENT on #1, fire from #2
# ---------------------------------------------------------------------------

class TestBashCmdTrigger:
    def test_bash_rm_rf_silent_on_first_occurrence(self, tmp_path):
        """'rm -rf' on first occurrence is SILENT — first use is likely intentional."""
        env = {"IATROGENICS_COUNTER_DIR": str(tmp_path)}
        rc, out, _ = run_hook(
            {"tool_name": "Bash", "tool_input": {"command": "rm -rf /tmp/testdir"},
             "session_id": "irr-rm-1st"},
            env_extra=env,
        )
        assert rc == 0
        assert not fired(out), "First Bash-command occurrence must be silent"

    def test_bash_rm_rf_fires_on_second_occurrence(self, tmp_path):
        """'rm -rf' fires on the SECOND occurrence (recurrence established)."""
        env = {"IATROGENICS_COUNTER_DIR": str(tmp_path), "IATROGENICS_K": "3",
               "CALIBRATED_SILENCE": "off"}
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "rm -rf /tmp/testdir"},
            "session_id": "irr-rm-2nd",
        }
        # First call: silent (counter→1)
        rc, out, _ = run_hook(payload, env_extra=env)
        assert rc == 0
        assert not fired(out)
        # Second call: fires (occurrence 2/3)
        rc, out, _ = run_hook(payload, env_extra=env)
        assert rc == 0
        assert fired(out)
        ctx = ctx_of(out)
        assert "2/3" in ctx
        assert "watchful-waiting" in ctx.lower() or "IATROGENICS" in ctx

    def test_bash_rm_force_silent_on_first(self, tmp_path):
        """'rm -f' first occurrence is silent."""
        env = {"IATROGENICS_COUNTER_DIR": str(tmp_path)}
        rc, out, _ = run_hook(
            {"tool_name": "Bash", "tool_input": {"command": "rm -f /tmp/lock.pid"},
             "session_id": "irr-rmf"},
            env_extra=env,
        )
        assert rc == 0
        assert not fired(out)

    def test_bash_git_reset_hard_silent_on_first(self, tmp_path):
        """'git reset --hard' first occurrence is silent."""
        env = {"IATROGENICS_COUNTER_DIR": str(tmp_path)}
        rc, out, _ = run_hook(
            {"tool_name": "Bash",
             "tool_input": {"command": "git reset --hard HEAD~1"},
             "session_id": "irr-gitreset"},
            env_extra=env,
        )
        assert rc == 0
        assert not fired(out)

    def test_bash_git_push_force_silent_on_first(self, tmp_path):
        """'git push --force' first occurrence is silent."""
        env = {"IATROGENICS_COUNTER_DIR": str(tmp_path)}
        rc, out, _ = run_hook(
            {"tool_name": "Bash",
             "tool_input": {"command": "git push origin main --force"},
             "session_id": "irr-gitpush"},
            env_extra=env,
        )
        assert rc == 0
        assert not fired(out)

    def test_mitmdump_silent_on_first(self, tmp_path):
        """mitmdump first occurrence is silent."""
        env = {"IATROGENICS_COUNTER_DIR": str(tmp_path)}
        rc, out, _ = run_hook(
            {"tool_name": "Bash",
             "tool_input": {"command": "mitmdump -s bc_inject.py -p 8080"},
             "session_id": "irr-mitm"},
            env_extra=env,
        )
        assert rc == 0
        assert not fired(out)

    def test_inject_occurrence_info_on_second_call(self, tmp_path):
        """Advisory on second Bash occurrence must state the occurrence number."""
        env = {"IATROGENICS_COUNTER_DIR": str(tmp_path), "IATROGENICS_K": "3",
               "CALIBRATED_SILENCE": "off"}
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "rm -rf /tmp/d"},
            "session_id": "irr-occ",
        }
        # First call: silent
        run_hook(payload, env_extra=env)
        # Second call: fires with "occurrence 2/3"
        rc, out, _ = run_hook(payload, env_extra=env)
        assert rc == 0
        assert fired(out)
        ctx = ctx_of(out)
        assert "2/3" in ctx


# ---------------------------------------------------------------------------
# Counter mechanics
# ---------------------------------------------------------------------------

class TestCounterMechanics:
    def test_bash_cmd_silences_after_k_plus_one_total(self, tmp_path):
        """For Bash commands: first occurrence is silent; fires K-1 times in K runs;
        the run after K total calls is also silent (count >= K)."""
        k = 3
        env = {"IATROGENICS_COUNTER_DIR": str(tmp_path), "IATROGENICS_K": str(k),
               "CALIBRATED_SILENCE": "off"}
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "rm -rf /tmp/counter_test_dir"},
            "session_id": "counter-session",
        }
        fired_counts = 0
        for _ in range(k):
            rc, out, _ = run_hook(payload, env_extra=env)
            assert rc == 0
            if fired(out):
                fired_counts += 1

        # First call is silent (skip), remaining k-1 calls fire.
        assert fired_counts == k - 1, (
            f"Expected {k - 1} fires in {k} runs (first is silent), got {fired_counts}"
        )

        # k+1th attempt: count == k >= K → silent (recurrence exhausted)
        rc, out, _ = run_hook(payload, env_extra=env)
        assert rc == 0
        assert not fired(out)

    def test_different_targets_independent_counters(self, tmp_path):
        """Two different targets have independent counters."""
        k = 2
        env = {"IATROGENICS_COUNTER_DIR": str(tmp_path), "IATROGENICS_K": str(k),
               "CALIBRATED_SILENCE": "off"}
        sess = "multi-target"
        payload_a = {"tool_name": "Bash",
                     "tool_input": {"command": "rm -rf /tmp/target_a"},
                     "session_id": sess}
        payload_b = {"tool_name": "Bash",
                     "tool_input": {"command": "rm -rf /tmp/target_b"},
                     "session_id": sess}

        # Exhaust target_a: call1=silent, call2=fire, call3=silent (count>=K)
        run_hook(payload_a, env_extra=env)   # call 1: count=0, silent
        run_hook(payload_a, env_extra=env)   # call 2: count=1, fires
        rc, out, _ = run_hook(payload_a, env_extra=env)  # call 3: count=2>=K, silent
        assert not fired(out)  # exhausted

        # target_b is independent: count=0 → silent (first occurrence)
        rc, out, _ = run_hook(payload_b, env_extra=env)
        assert rc == 0
        assert not fired(out)  # independent counter, first occurrence → silent

        # target_b second call fires (count=1 < K=2)
        rc, out, _ = run_hook(payload_b, env_extra=env)
        assert rc == 0
        assert fired(out)

    def test_counter_auto_clears_after_ttl(self, tmp_path):
        """Counter file older than TTL is discarded; MCP tool advisory fires again."""
        env = {"IATROGENICS_COUNTER_DIR": str(tmp_path),
               "IATROGENICS_K": "1",
               "IATROGENICS_TTL_HOURS": "0.0001",  # ~0.36 seconds
               "CALIBRATED_SILENCE": "off"}
        # Use an MCP tool (fires on first occurrence, unaffected by cmd-triggered skip)
        payload = {
            "tool_name": "mcp__cheatengine__write_integer",
            "tool_input": {"address": "0x1000", "value": 0},
            "session_id": "ttl-session",
        }
        # First call: fires (MCP tool, K=1, count=0 < K=1)
        rc, out, _ = run_hook(payload, env_extra=env)
        assert rc == 0
        assert fired(out)

        # Second call immediately: should NOT fire (count=1 >= K=1)
        rc, out, _ = run_hook(payload, env_extra=env)
        assert rc == 0
        assert not fired(out)

        # Wait for TTL to expire, then call again: counter cleared → fires again
        time.sleep(1.5)
        rc, out, _ = run_hook(payload, env_extra=env)
        assert rc == 0
        assert fired(out)  # fresh after TTL expiry


# ---------------------------------------------------------------------------
# Calibrated-silence gate
# ---------------------------------------------------------------------------

class TestCalibratedSilenceGate:
    def test_cs_suppresses_mcp_tool_inject(self, tmp_path):
        """When calibrated-silence suppresses, hook is silent even for MCP tool (first occ.)."""
        ledger = tmp_path / "interjections.jsonl"
        _make_suppressing_ledger(ledger, "suggestion")
        env = {
            "IATROGENICS_COUNTER_DIR": str(tmp_path / "counters"),
            "CALSIL_LEDGER_PATH": str(ledger),
        }
        # MCP tool → normally fires on first occurrence; CS should suppress it
        rc, out, _ = run_hook(
            {"tool_name": "mcp__cheatengine__write_integer",
             "tool_input": {"address": "0x1000", "value": 0},
             "session_id": "cs-suppress-test"},
            env_extra=env,
        )
        assert rc == 0
        assert not fired(out), "Calibrated-silence suppressed; hook should be silent"

    def test_cs_disabled_still_allows_mcp_inject(self, tmp_path):
        """CALIBRATED_SILENCE=off → should_interject returns allow → hook fires."""
        env = {
            "IATROGENICS_COUNTER_DIR": str(tmp_path),
            "CALIBRATED_SILENCE": "off",
        }
        rc, out, _ = run_hook(
            {"tool_name": "mcp__cheatengine__write_integer",
             "tool_input": {"address": "0x1000", "value": 0},
             "session_id": "cs-off-test"},
            env_extra=env,
        )
        assert rc == 0
        assert fired(out), "CS disabled → fail-open allow → hook must fire"

    def test_cs_suppresses_bash_second_occurrence(self, tmp_path):
        """When CS suppresses, Bash second occurrence is also silent."""
        ledger = tmp_path / "interjections.jsonl"
        _make_suppressing_ledger(ledger, "suggestion")
        env = {
            "IATROGENICS_COUNTER_DIR": str(tmp_path / "counters"),
            "CALSIL_LEDGER_PATH": str(ledger),
            "IATROGENICS_K": "3",
        }
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "rm -rf /tmp/cs-test"},
            "session_id": "cs-bash-test",
        }
        # Call 1: cmd_triggered + count=0 → silent (first-occurrence skip)
        run_hook(payload, env_extra=env)
        # Call 2: CS suppresses (count=1 would fire, but CS prevents it)
        rc, out, _ = run_hook(payload, env_extra=env)
        assert rc == 0
        assert not fired(out)


# ---------------------------------------------------------------------------
# L4: input-size cap
# ---------------------------------------------------------------------------

class TestInputSizeCap:
    def test_huge_command_does_not_hang(self, tmp_path):
        """A command >256KB does not cause a hang or crash (size cap applied)."""
        env = {"IATROGENICS_COUNTER_DIR": str(tmp_path)}
        huge_cmd = "ls " + "x" * (300 * 1024)  # ~300KB
        rc, out, err = run_hook(
            {"tool_name": "Bash", "tool_input": {"command": huge_cmd},
             "session_id": "size-cap-test"},
            env_extra=env,
            timeout=10,
        )
        assert rc == 0  # must not crash

    def test_huge_irreversible_cmd_truncated_to_silence(self, tmp_path):
        """A huge command where the irreversible pattern appears only beyond 256KB
        should NOT fire (truncation hides it — acceptable trade-off for safety)."""
        env = {"IATROGENICS_COUNTER_DIR": str(tmp_path)}
        # Pattern is past the 256KB mark
        padding = "x" * (256 * 1024 + 100)
        cmd = padding + " rm -rf /tmp/late"
        rc, out, _ = run_hook(
            {"tool_name": "Bash", "tool_input": {"command": cmd},
             "session_id": "size-cap-miss"},
            env_extra=env,
        )
        assert rc == 0
        assert not fired(out)  # pattern beyond cap → not scanned → silent


# ---------------------------------------------------------------------------
# Fail-open tests
# ---------------------------------------------------------------------------

class TestFailOpen:
    def test_malformed_stdin(self):
        """Completely invalid JSON on stdin -> exit 0, no crash."""
        p = subprocess.run(
            [sys.executable, HOOK],
            input="not{{{{json",
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert p.returncode == 0

    def test_empty_stdin(self):
        """Empty stdin -> exit 0."""
        p = subprocess.run(
            [sys.executable, HOOK],
            input="",
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert p.returncode == 0

    def test_no_tool_name(self, tmp_path):
        """Payload without tool_name -> exit 0 regardless (cmd still evaluated)."""
        env = {"IATROGENICS_COUNTER_DIR": str(tmp_path)}
        rc, out, _ = run_hook(
            {"tool_input": {"command": "rm -rf /tmp/x"}, "session_id": "nt"},
            env_extra=env,
        )
        assert rc == 0


# ---------------------------------------------------------------------------
# Opt-out tests
# ---------------------------------------------------------------------------

class TestOptOut:
    def test_env_off(self, tmp_path):
        """IATROGENICS=off -> silent even for an irreversible payload."""
        env = {"IATROGENICS_COUNTER_DIR": str(tmp_path), "IATROGENICS": "off"}
        rc, out, _ = run_hook(
            {"tool_name": "Bash",
             "tool_input": {"command": "rm -rf /tmp/foo"},
             "session_id": "opt-env"},
            env_extra=env,
        )
        assert rc == 0
        assert not fired(out)

    def test_env_zero(self, tmp_path):
        """IATROGENICS=0 -> silent."""
        env = {"IATROGENICS_COUNTER_DIR": str(tmp_path), "IATROGENICS": "0"}
        rc, out, _ = run_hook(
            {"tool_name": "mcp__cheatengine__write_integer",
             "tool_input": {"address": "0x1000", "value": 0},
             "session_id": "opt-zero"},
            env_extra=env,
        )
        assert rc == 0
        assert not fired(out)

    def test_disabled_file(self, tmp_path):
        """.disabled file in hook dir -> silent even for irreversible payload."""
        disabled = HERE / ".disabled"
        try:
            disabled.touch()
            env = {"IATROGENICS_COUNTER_DIR": str(tmp_path)}
            rc, out, _ = run_hook(
                {"tool_name": "Bash",
                 "tool_input": {"command": "rm -rf /tmp/bar"},
                 "session_id": "opt-dis"},
                env_extra=env,
            )
            assert rc == 0
            assert not fired(out)
        finally:
            disabled.unlink(missing_ok=True)
