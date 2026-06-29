#!/usr/bin/env python3
"""pytest tests for contraindication/check.py.

Run:  pytest test_check.py -v
      python -m pytest test_check.py -v   (from the hooks/contraindication dir)

Covers:
  - no-trigger (silent), including plain Interceptor.attach without hot-path keywords
  - trigger-hit (correct inject), including FRIDA row requiring hot-path context
  - FRIDA-HOTPATH-HOOK narrow pattern: only fires on render-thread/high-freq indicators
  - calibrated-silence gate: suppresses when ledger indicates noise; fail-open when disabled
  - fail-open (bad stdin)
  - opt-out (env var + .disabled file)
  - bg-active gate for PARA-GIT-ADD
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
HOOK = str(HERE / "check.py")


# ---------------------------------------------------------------------------
# Helpers shared across all tests
# ---------------------------------------------------------------------------

def run_hook(payload: dict, env_extra: dict | None = None, timeout: int = 15) -> tuple[int, str, str]:
    """Run check.py as a subprocess with the given JSON payload on stdin."""
    import subprocess
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
    """True when the hook emitted a non-empty additionalContext."""
    if not stdout:
        return False
    try:
        parsed = json.loads(stdout)
        ctx = parsed.get("hookSpecificOutput", {}).get("additionalContext", "")
        return bool(ctx)
    except Exception:
        return False


def ctx_of(stdout: str) -> str:
    """Extract additionalContext text; returns '' if absent."""
    try:
        return json.loads(stdout)["hookSpecificOutput"]["additionalContext"]
    except Exception:
        return ""


def _make_suppressing_ledger(path: Path, itype: str, count: int = 10) -> None:
    """Write enough 'ignored' rows to force calibrated-silence to suppress.

    Wilson center with 0 acted / 10 ignored ≈ 0.14; value(gem)=1.3 → ev≈0.18
    which is below the default BASE_THRESHOLD of 0.40, so should_interject returns False.
    """
    rows = []
    base_ts = time.time() - count * 120
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
# Hermetic CS state for every test (isolation regression fix)
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _isolate_cs_state(tmp_path, monkeypatch):
    """Make every test deterministic regardless of the LIVE production CS ledger.

    - Fresh per-test seen-dir so each contraindication is 'distinct' (deterministic
      distinct-vs-repeat classification, independent of prior runs / sessions).
    - Empty CS ledger by default so any repeat-path CS gate is cold-start (allow),
      never the stuffed production ledger. CS-gate tests override CALSIL_LEDGER_PATH
      with their OWN stuffed/fresh ledger and force CS active via CALIBRATED_SILENCE="".

    Mirrors the iatrogenics/test_gate.py isolation pattern (which passes 30/30).
    """
    monkeypatch.setenv("CONTRAINDICATION_SEEN_DIR", str(tmp_path / "cseen"))
    empty_ledger = tmp_path / "cs_empty.jsonl"
    empty_ledger.write_text("", encoding="utf-8")
    monkeypatch.setenv("CALSIL_LEDGER_PATH", str(empty_ledger))


# ---------------------------------------------------------------------------
# No-trigger tests
# ---------------------------------------------------------------------------

class TestNoTrigger:
    def test_unmatched_tool_read(self):
        """Read tool does not match any row — silent."""
        rc, out, _ = run_hook({"tool_name": "Read", "tool_input": {"file_path": "/tmp/x"}})
        assert rc == 0
        assert not fired(out)

    def test_bash_innocuous_ls(self):
        """Plain 'ls -la' command — no match, silent."""
        rc, out, _ = run_hook({"tool_name": "Bash", "tool_input": {"command": "ls -la"}})
        assert rc == 0
        assert not fired(out)

    def test_bash_git_add_specific_file(self):
        """'git add src/foo.py' is fine (not -A or .)  — no match."""
        rc, out, _ = run_hook({
            "tool_name": "Bash",
            "tool_input": {"command": "git add src/foo.py && git commit -m 'fix'"},
        })
        assert rc == 0
        assert not fired(out)

    def test_frida_safe_operation(self):
        """Frida enumerate_processes has no dangerous input pattern — no match."""
        rc, out, _ = run_hook({
            "tool_name": "mcp__frida-mcp__enumerate_processes",
            "tool_input": {},
        })
        assert rc == 0
        assert not fired(out)

    def test_bash_dev_null_redirect(self):
        """Redirect to /dev/null is excluded from MSYS-DEVICE-REDIR — no match."""
        rc, out, _ = run_hook({
            "tool_name": "Bash",
            "tool_input": {"command": "some_command 2>/dev/null"},
        })
        assert rc == 0
        assert not fired(out)

    def test_bash_dev_stderr_redirect(self):
        """Redirect to /dev/stderr is excluded — no match."""
        rc, out, _ = run_hook({
            "tool_name": "Bash",
            "tool_input": {"command": "echo msg >/dev/stderr"},
        })
        assert rc == 0
        assert not fired(out)

    def test_para_git_add_without_bg_tasks(self):
        """PARA-GIT-ADD only fires with running async bg tasks — empty dir = no match."""
        with tempfile.TemporaryDirectory() as td:
            rc, out, _ = run_hook(
                {"tool_name": "Bash", "tool_input": {"command": "git add -A"}},
                env_extra={"BG_REGISTRY_DIR": td},
            )
        assert rc == 0
        assert not fired(out)

    def test_frida_plain_interceptor_attach_no_fire(self):
        """FRIDA-HOTPATH-HOOK does NOT fire for a plain Interceptor.attach without
        any render-thread / high-frequency context keywords.

        The user does heavy legitimate Frida RE with plain attaches; the narrowed
        input_pattern requires a hot-path indicator (getGlobal, per-frame, render-thread,
        etc.) — not just the presence of Interceptor.attach.
        """
        rc, out, _ = run_hook({
            "tool_name": "mcp__frida-mcp__create_simple_hook",
            "tool_input": {
                "script": (
                    "Interceptor.attach(ptr(0x1000), {"
                    "onEnter: function(args) { send(args[0].toInt32()); }"
                    "});"
                ),
            },
        })
        assert rc == 0
        assert not fired(out), (
            "Plain Interceptor.attach without hot-path keywords must not fire FRIDA row"
        )

    def test_frida_onenter_only_no_fire(self):
        """A script with onEnter but no hot-path keyword does NOT trigger FRIDA row."""
        rc, out, _ = run_hook({
            "tool_name": "mcp__frida-mcp__execute_in_session",
            "tool_input": {
                "session_id": "s1",
                "script": "Interceptor.attach(Module.findExportByName(null, 'malloc'), {onEnter: function(args){}});",
            },
        })
        assert rc == 0
        assert not fired(out)


# ---------------------------------------------------------------------------
# Trigger-hit tests
# ---------------------------------------------------------------------------

class TestTriggerHit:
    def test_frida_hotpath_interceptor_attach_with_getglobal(self):
        """FRIDA-HOTPATH-HOOK fires on create_simple_hook when getGlobal is in script."""
        rc, out, _ = run_hook({
            "tool_name": "mcp__frida-mcp__create_simple_hook",
            "tool_input": {
                "script": (
                    "Interceptor.attach(Module.findExportByName(null, 'getGlobal'), {"
                    "onEnter: function(args) { send(args[0]); }"
                    "});"
                ),
            },
        })
        assert rc == 0
        assert fired(out)
        ctx = ctx_of(out)
        assert "FRIDA-HOTPATH-HOOK" in ctx
        assert "crash" in ctx.lower() or "hook" in ctx.lower()

    def test_frida_hotpath_execute_session(self):
        """FRIDA-HOTPATH-HOOK fires on execute_in_session with getGlobal reference."""
        rc, out, _ = run_hook({
            "tool_name": "mcp__frida-mcp__execute_in_session",
            "tool_input": {"session_id": "s1", "script": "getGlobal('renderer')"},
        })
        assert rc == 0
        assert fired(out)
        assert "FRIDA-HOTPATH-HOOK" in ctx_of(out)

    def test_frida_hotpath_per_frame_keyword(self):
        """FRIDA-HOTPATH-HOOK fires when script contains per-frame hook pattern."""
        rc, out, _ = run_hook({
            "tool_name": "mcp__frida-mcp__execute_in_session",
            "tool_input": {
                "session_id": "s1",
                "script": "// hook called per-frame in render loop",
            },
        })
        assert rc == 0
        assert fired(out)
        assert "FRIDA-HOTPATH-HOOK" in ctx_of(out)

    def test_frida_hotpath_render_thread_keyword(self):
        """FRIDA-HOTPATH-HOOK fires when script mentions render-thread."""
        rc, out, _ = run_hook({
            "tool_name": "mcp__frida-mcp__execute_in_session",
            "tool_input": {
                "session_id": "s1",
                "script": "// intercept render-thread function at 0x8A3350",
            },
        })
        assert rc == 0
        assert fired(out)

    def test_semgrep_pro_flag(self):
        """SEMGREP-PRO-MCP-RAM fires when semgrep is called with --pro."""
        rc, out, _ = run_hook({
            "tool_name": "Bash",
            "tool_input": {"command": "semgrep scan --pro src/"},
        })
        assert rc == 0
        assert fired(out)
        ctx = ctx_of(out)
        assert "SEMGREP-PRO-MCP-RAM" in ctx
        assert "RAM" in ctx or "OOM" in ctx or "920" in ctx

    def test_semgrep_plugin_reference(self):
        """SEMGREP-PRO-MCP-RAM fires on 'plugin:semgrep' string in input."""
        rc, out, _ = run_hook({
            "tool_name": "Bash",
            "tool_input": {"command": "plugin:semgrep scan src/"},
        })
        assert rc == 0
        assert fired(out)
        assert "SEMGREP-PRO-MCP-RAM" in ctx_of(out)

    def test_bc_mitm_mitmdump(self):
        """BC-MITM-CACHEBUSTED fires when mitmdump is invoked."""
        rc, out, _ = run_hook({
            "tool_name": "Bash",
            "tool_input": {"command": "mitmdump -s inject.py -p 8080"},
        })
        assert rc == 0
        assert fired(out)
        ctx = ctx_of(out)
        assert "BC-MITM-CACHEBUSTED" in ctx
        assert "HGT" in ctx or "Battle Cats" in ctx or "MITM" in ctx

    def test_bc_mitm_mitmproxy(self):
        """BC-MITM-CACHEBUSTED fires on mitmproxy too."""
        rc, out, _ = run_hook({
            "tool_name": "Bash",
            "tool_input": {"command": "mitmproxy --listen-port 8888"},
        })
        assert rc == 0
        assert fired(out)
        assert "BC-MITM-CACHEBUSTED" in ctx_of(out)

    def test_msys_device_redirect(self):
        """MSYS-DEVICE-REDIR fires on redirect to /dev/tty."""
        rc, out, _ = run_hook({
            "tool_name": "Bash",
            "tool_input": {"command": "echo hello > /dev/tty"},
        })
        assert rc == 0
        assert fired(out)
        ctx = ctx_of(out)
        assert "MSYS-DEVICE-REDIR" in ctx
        assert "0-byte" in ctx or "Windows" in ctx or "MSYS" in ctx

    def test_para_git_add_all_with_bg_active(self):
        """PARA-GIT-ADD fires with 'git add -A' when a running async task is in bg-registry."""
        with tempfile.TemporaryDirectory() as td:
            record = {
                "id": "task-abc",
                "kind": "Task",
                "status": "running",
                "sync": False,
                "started_ts": time.time() - 30,
            }
            (Path(td) / "session-test.ndjson").write_text(
                json.dumps(record) + "\n", encoding="utf-8"
            )
            rc, out, _ = run_hook(
                {"tool_name": "Bash", "tool_input": {"command": "git add -A"}},
                env_extra={"BG_REGISTRY_DIR": td},
            )
        assert rc == 0
        assert fired(out)
        ctx = ctx_of(out)
        assert "PARA-GIT-ADD" in ctx
        assert "git index" in ctx.lower() or "worktree" in ctx.lower()

    def test_para_git_add_dot_with_bg_active(self):
        """PARA-GIT-ADD also fires on 'git add .' (dot variant)."""
        with tempfile.TemporaryDirectory() as td:
            record = {"id": "t2", "kind": "Task", "status": "running",
                      "sync": False, "started_ts": time.time()}
            (Path(td) / "s.ndjson").write_text(json.dumps(record) + "\n", encoding="utf-8")
            rc, out, _ = run_hook(
                {"tool_name": "Bash", "tool_input": {"command": "git add . && git commit"}},
                env_extra={"BG_REGISTRY_DIR": td},
            )
        assert rc == 0
        assert fired(out)
        assert "PARA-GIT-ADD" in ctx_of(out)

    def test_inject_contains_safe_alternative(self):
        """Every hit must include a SAFE ALTERNATIVE section.

        Uses a script that contains the 'getGlobal' hot-path keyword so it matches
        the narrowed FRIDA-HOTPATH-HOOK input_pattern.
        """
        rc, out, _ = run_hook({
            "tool_name": "mcp__frida-mcp__create_simple_hook",
            "tool_input": {
                "script": (
                    "Interceptor.attach(ptr(0x1000), {"
                    "onEnter: function(){ getGlobal('x'); }"
                    "});"
                ),
            },
        })
        assert rc == 0
        assert fired(out)
        ctx = ctx_of(out)
        assert "SAFE ALTERNATIVE" in ctx


# ---------------------------------------------------------------------------
# Calibrated-silence gate
# ---------------------------------------------------------------------------

class TestCalibratedSilenceGate:
    """Calibrated-silence must DEDUP exact repeats, never gag a NEW/distinct harm
    warning. Each test sets up its OWN tmp ledger (and forces CS active via
    CALIBRATED_SILENCE="") so it tests the gate deterministically, not the live ledger.
    """

    def test_cs_does_not_suppress_distinct_when_ledger_stuffed(self, tmp_path):
        """SAFETY: a NEW/distinct contraindication MUST fire even when the CS ledger is
        stuffed with ignored 'gem' rows — a real harm warning must never be silenced
        just because the session is long/noisy."""
        ledger = tmp_path / "interjections.jsonl"
        _make_suppressing_ledger(ledger, "gem")
        rc, out, _ = run_hook(
            {"tool_name": "Bash",
             "tool_input": {"command": "mitmdump -s inject.py -p 8080"},
             "session_id": "cs-distinct-test"},
            env_extra={"CALSIL_LEDGER_PATH": str(ledger), "CALIBRATED_SILENCE": ""},
        )
        assert rc == 0
        assert fired(out), "Distinct contraindication must bypass CS and fire"
        assert "BC-MITM-CACHEBUSTED" in ctx_of(out)

    def test_cs_suppresses_repeat_registry_hit(self, tmp_path):
        """DEDUP: an exact REPEAT of an already-surfaced contraindication (same id, same
        session) IS deduped by CS when the ledger is stuffed."""
        ledger = tmp_path / "interjections.jsonl"
        _make_suppressing_ledger(ledger, "gem")
        env = {"CALSIL_LEDGER_PATH": str(ledger), "CALIBRATED_SILENCE": ""}
        payload = {"tool_name": "Bash",
                   "tool_input": {"command": "semgrep scan --pro src/"},
                   "session_id": "cs-repeat-test"}
        # 1st call: distinct -> bypasses CS -> fires (new safety alert).
        rc, out, _ = run_hook(payload, env_extra=env)
        assert rc == 0
        assert fired(out)
        # 2nd identical call: repeat -> CS gate with stuffed ledger -> suppressed.
        rc, out, _ = run_hook(payload, env_extra=env)
        assert rc == 0
        assert not fired(out), "Exact repeat should be deduped by calibrated-silence"

    def test_cs_disabled_still_allows_inject(self):
        """CALIBRATED_SILENCE=off → should_interject returns allow → hook fires."""
        rc, out, _ = run_hook(
            {"tool_name": "Bash",
             "tool_input": {"command": "semgrep scan --pro src/"},
             "session_id": "cs-off-test"},
            env_extra={"CALIBRATED_SILENCE": "off"},
        )
        assert rc == 0
        assert fired(out), "CS disabled → fail-open allow → hook must fire"

    def test_cs_ledger_path_honoured_on_repeat(self, tmp_path):
        """CALSIL_LEDGER_PATH is threaded through to should_interject on the REPEAT path.

        A fresh (empty) ledger is cold-start so even a repeat is allowed; a stuffed
        ledger suppresses the repeat. The DISTINCT first call always fires either way.
        """
        # Fresh (empty) ledger — repeat still allowed (cold-start).
        fresh_ledger = tmp_path / "fresh.jsonl"
        fresh_ledger.write_text("", encoding="utf-8")
        env_fresh = {"CALSIL_LEDGER_PATH": str(fresh_ledger), "CALIBRATED_SILENCE": ""}
        payload_fresh = {"tool_name": "Bash",
                         "tool_input": {"command": "semgrep scan --pro src/"},
                         "session_id": "cs-fresh"}
        rc, out, _ = run_hook(payload_fresh, env_extra=env_fresh)
        assert rc == 0
        assert fired(out)  # distinct
        rc, out, _ = run_hook(payload_fresh, env_extra=env_fresh)
        assert rc == 0
        assert fired(out)  # repeat, but cold-start ledger -> allow

        # Stuffed ledger — repeat suppressed.
        stuffed_ledger = tmp_path / "stuffed.jsonl"
        _make_suppressing_ledger(stuffed_ledger, "gem")
        env_stuffed = {"CALSIL_LEDGER_PATH": str(stuffed_ledger), "CALIBRATED_SILENCE": ""}
        payload_stuffed = {"tool_name": "Bash",
                           "tool_input": {"command": "semgrep scan --pro src/"},
                           "session_id": "cs-stuffed"}
        rc, out, _ = run_hook(payload_stuffed, env_extra=env_stuffed)
        assert rc == 0
        assert fired(out)  # distinct
        rc, out, _ = run_hook(payload_stuffed, env_extra=env_stuffed)
        assert rc == 0
        assert not fired(out)  # repeat suppressed by stuffed ledger


# ---------------------------------------------------------------------------
# Fail-open tests
# ---------------------------------------------------------------------------

class TestFailOpen:
    def test_malformed_stdin(self):
        """Completely invalid JSON on stdin -> exit 0, no crash."""
        import subprocess
        p = subprocess.run(
            [sys.executable, HOOK],
            input="not-json{{{{",
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert p.returncode == 0

    def test_empty_stdin(self):
        """Empty stdin -> exit 0."""
        import subprocess
        p = subprocess.run(
            [sys.executable, HOOK],
            input="",
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert p.returncode == 0

    def test_missing_tool_name(self):
        """Payload without tool_name -> exit 0, no inject (no pattern match)."""
        rc, out, _ = run_hook({"tool_input": {"command": "semgrep --pro src/"}})
        assert rc == 0
        assert not fired(out)

    def test_corrupted_registry_file(self, tmp_path, monkeypatch):
        """If contraindications.json is corrupt, still exit 0 (fail-open)."""
        bad_registry = tmp_path / "contraindications.json"
        bad_registry.write_text("{{not valid json", encoding="utf-8")
        import subprocess
        dict(os.environ)
        _payload_repr = repr(json.dumps({"tool_name": "Bash", "tool_input": {"command": "semgrep --pro"}}))
        p = subprocess.run(
            [sys.executable, "-c",
             f"import sys, json; sys.path.insert(0, {repr(str(HERE))}); "
             f"import check; "
             f"check.REGISTRY = __import__('pathlib').Path({repr(str(bad_registry))}); "
             f"sys.stdin = __import__('io').StringIO({_payload_repr}); "
             f"sys.exit(check.main())"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert p.returncode == 0


# ---------------------------------------------------------------------------
# Opt-out tests
# ---------------------------------------------------------------------------

class TestOptOut:
    def test_env_off(self):
        """CONTRAINDICATION=off -> silent even for a known-hit payload."""
        rc, out, _ = run_hook(
            {"tool_name": "Bash", "tool_input": {"command": "semgrep scan --pro src/"}},
            env_extra={"CONTRAINDICATION": "off"},
        )
        assert rc == 0
        assert not fired(out)

    def test_env_zero(self):
        """CONTRAINDICATION=0 -> silent."""
        rc, out, _ = run_hook(
            {"tool_name": "Bash", "tool_input": {"command": "semgrep --pro src/"}},
            env_extra={"CONTRAINDICATION": "0"},
        )
        assert rc == 0
        assert not fired(out)

    def test_disabled_file(self):
        """.disabled file in hook dir -> silent even for a known-hit payload."""
        disabled = HERE / ".disabled"
        try:
            disabled.touch()
            rc, out, _ = run_hook({
                "tool_name": "Bash",
                "tool_input": {"command": "semgrep scan --pro src/"},
            })
            assert rc == 0
            assert not fired(out)
        finally:
            disabled.unlink(missing_ok=True)
