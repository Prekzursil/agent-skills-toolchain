#!/usr/bin/env python3
"""Blocking-mode regression tests (2026-10-17 consolidation wave).

``exec`` checks must run as subprocesses whose REAL exit code, stderr and
decision JSON survive the dispatcher: an exit-2 block must make the dispatcher
itself exit 2 with the check's stderr; a deny decision JSON must be forwarded
verbatim; a hung exec check must fail open. If any of these break, the 7
consolidated PreToolUse guards are silently disarmed while looking healthy.

2026-10-18 review-thread extension (PR #374 Codex review): bypass-notice
surfacing on SUCCESSFUL blocking_rc checks, advisory-context preservation
around forwarded/denied decisions, launch-failure attestation, and tree-kill
of timed-out exec children (no orphaned grandchildren).

Run: pytest hooks/_dispatch/test_blocking_mode.py -q
"""
from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent


def load_dispatch():
    spec = importlib.util.spec_from_file_location("dispatch_mod_bm", HERE / "dispatch.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write(root: Path, rel: str, body: str) -> str:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    return str(p)


def _run_cli(payload: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(HERE / "dispatch.py"), "pretooluse"],
        input=payload, capture_output=True, text=True, timeout=120,
    )


def test_blocking_exit2_propagates(tmp_path):
    script = _write(tmp_path, "blocker/guard.py",
        "import sys\n"
        "sys.stderr.write('BLOCKED-REASON-XYZ\\n')\n"
        "sys.exit(2)\n")
    manifest = {
        "hooks_root": str(tmp_path),
        "events": {"PreToolUse": {"checks": [
            {"name": "blocker", "script": "blocker/guard.py", "timeout": 8,
             "matcher": "Bash", "exec": True, "blocking_rc": True},
        ]}},
    }
    (tmp_path / "_dispatch_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    # point the dispatcher at our manifest via monkeypatched path: run() directly instead
    mod = load_dispatch()
    records: list = []
    out = mod.run("PreToolUse", '{"tool_name":"Bash"}', manifest, collect=records)
    assert out is None
    assert records and records[0]["rc"] == 2
    assert "BLOCKED-REASON-XYZ" in records[0]["err"]


def test_cli_blocking_exit2_end_to_end(tmp_path, monkeypatch):
    script = _write(tmp_path, "blocker/guard.py",
        "import sys\n"
        "sys.stderr.write('force-push refused\\n')\n"
        "sys.exit(2)\n")
    # reuse the REAL manifest mechanism: temporarily write our own manifest
    real = HERE / "manifest.json"
    backup = real.read_text(encoding="utf-8")
    try:
        real.write_text(json.dumps({
            "hooks_root": str(tmp_path),
            "events": {"PreToolUse": {"checks": [
                {"name": "blocker", "script": script, "timeout": 8,
                 "matcher": "Bash", "exec": True, "blocking_rc": True},
            ]}},
        }), encoding="utf-8")
        p = _run_cli('{"tool_name":"Bash","tool_input":{"command":"x"}}')
        assert p.returncode == 2, f"expected exit 2, got {p.returncode}: {p.stderr!r}"
        assert "force-push refused" in p.stderr
    finally:
        real.write_text(backup, encoding="utf-8")


def test_decision_json_forwarded(tmp_path):
    script = _write(tmp_path, "denier/deny.py",
        "import json, sys\n"
        "print(json.dumps({'hookSpecificOutput': {'permissionDecision': 'deny',"
        " 'permissionDecisionReason': 'creds'}}))\n"
        "sys.exit(0)\n")
    real = HERE / "manifest.json"
    backup = real.read_text(encoding="utf-8")
    try:
        real.write_text(json.dumps({
            "hooks_root": str(tmp_path),
            "events": {"PreToolUse": {"checks": [
                {"name": "denier", "script": script, "timeout": 8,
                 "matcher": "Read", "exec": True, "decision": True},
            ]}},
        }), encoding="utf-8")
        p = _run_cli('{"tool_name":"Read","tool_input":{"file_path":"x"}}')
        assert p.returncode == 0
        obj = json.loads(p.stdout.strip().splitlines()[-1])
        assert obj["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert obj["hookSpecificOutput"]["permissionDecisionReason"] == "creds"
    finally:
        real.write_text(backup, encoding="utf-8")


def test_hung_exec_check_fails_open(tmp_path):
    script = _write(tmp_path, "hung/guard.py", "import time\ntime.sleep(30)\n")
    real = HERE / "manifest.json"
    backup = real.read_text(encoding="utf-8")
    try:
        real.write_text(json.dumps({
            "hooks_root": str(tmp_path),
            "events": {"PreToolUse": {"checks": [
                {"name": "hung", "script": script, "timeout": 2,
                 "matcher": "Bash", "exec": True, "blocking_rc": True},
            ]}},
        }), encoding="utf-8")
        p = _run_cli('{"tool_name":"Bash"}')
        assert p.returncode == 0, "a timed-out exec check must fail open"
        assert "timeout" in p.stderr  # receipt attests the loss
    finally:
        real.write_text(backup, encoding="utf-8")


# --------------------------------------------------------------------------- #
# 2026-10-18 review-thread regressions
# --------------------------------------------------------------------------- #

def _swap_manifest(tmp_path: Path, checks: list) -> str:
    """Point the REAL manifest at tmp_path checks; return the backup text."""
    real = HERE / "manifest.json"
    backup = real.read_text(encoding="utf-8")
    real.write_text(json.dumps({
        "hooks_root": str(tmp_path),
        "events": {"PreToolUse": {"checks": checks}},
    }), encoding="utf-8")
    return backup


def test_successful_bypass_notice_surfaces_on_stderr(tmp_path):
    """P1 thread: an allowed (rc=0) force-push bypass must not be silent.

    no-force-push under FORGE_NO_FORCE_PUSH_OFF/.disabled writes its break-glass
    notice to BOTH streams and exits 0. The dispatcher drops the plaintext
    stdout (it is not JSON) and used to forward stderr only on the rc!=0 block
    path, so the allowed force-push became invisible. It must reach the
    dispatcher's stderr, and the stdout JSON channel must stay untouched.
    """
    script = _write(tmp_path, "forge/hook.py",
        "import sys\n"
        "notice = ('no-force-push: GATE BYPASSED - a force-push was detected "
        "and NOT blocked\\n')\n"
        "sys.stdout.write(notice)\n"
        "sys.stderr.write(notice)\n"
        "sys.exit(0)\n")
    backup = _swap_manifest(tmp_path, [
        {"name": "forge", "script": script, "timeout": 8,
         "matcher": "Bash", "exec": True, "blocking_rc": True},
    ])
    try:
        p = _run_cli('{"tool_name":"Bash"}')
        assert p.returncode == 0, "bypass means allow (rc 0)"
        assert "GATE BYPASSED" in p.stderr, (
            "the break-glass notice must surface on stderr; it was dropped: "
            f"{p.stderr!r}"
        )
        assert p.stdout.strip() == "", (
            "stdout is the JSON channel and must stay empty for a plaintext "
            f"notice: {p.stdout!r}"
        )
    finally:
        (HERE / "manifest.json").write_text(backup, encoding="utf-8")


@pytest.mark.parametrize("decision_payload", [
    # inject-nopager shape: allow-with-rewrite (updatedCommand)
    {"updatedCommand": "GIT_PAGER=cat git log"},
    # deny-credential-reads shape: deny decision
    {"permissionDecision": "deny", "permissionDecisionReason": "creds"},
], ids=["rewrite", "deny"])
def test_forwarded_decision_carries_the_other_checks_context(
    tmp_path, decision_payload
):
    """P1b + MEDIUM threads: decision forwarding must not discard the aggregate.

    The standalone hooks each delivered their own output; after consolidation
    an inject-nopager rewrite (or a deny) used to make main() write ONLY the
    decision JSON, dropping the Ulysses/loop-recovery advisory context other
    selected checks had collected. The decision JSON must carry that context
    in hookSpecificOutput.additionalContext.
    """
    advisory = _write(tmp_path, "adv/check.py",
        "import json\n"
        "def main():\n"
        "    print(json.dumps({'hookSpecificOutput': "
        "{'additionalContext': 'ULYSSES: stay on the committed goal'}}))\n"
        "    return 0\n")
    decider = _write(tmp_path, "decide/guard.py",
        "import json, sys\n"
        "hso = {'hookSpecificOutput': " + json.dumps(decision_payload) + "}\n"
        "print(json.dumps(hso))\n"
        "sys.exit(0)\n")
    backup = _swap_manifest(tmp_path, [
        {"name": "adv", "script": advisory, "timeout": 8,
         "matcher": "Bash"},
        {"name": "decide", "script": decider, "timeout": 8,
         "matcher": "Bash", "exec": True, "decision": True},
    ])
    try:
        p = _run_cli('{"tool_name":"Bash"}')
        assert p.returncode == 0
        obj = json.loads(p.stdout.strip().splitlines()[-1])
        hso = obj["hookSpecificOutput"]
        for key, value in decision_payload.items():
            assert hso.get(key) == value, (
                f"the decision itself ({key}) must be forwarded verbatim: {obj!r}"
            )
        assert "ULYSSES: stay on the committed goal" in str(
            hso.get("additionalContext")
        ), f"advisory context was dropped by the forward: {obj!r}"
    finally:
        (HERE / "manifest.json").write_text(backup, encoding="utf-8")


def test_decision_does_not_duplicate_its_own_context(tmp_path):
    """CONTROL for the merge: the decision check's own additionalContext is not
    re-appended on top of itself (the aggregate excludes the decision's check)."""
    decider = _write(tmp_path, "decide/guard.py",
        "import json, sys\n"
        "print(json.dumps({'hookSpecificOutput': {'updatedCommand': 'x',"
        " 'additionalContext': 'FROM-DECIDER'}}))\n"
        "sys.exit(0)\n")
    backup = _swap_manifest(tmp_path, [
        {"name": "decide", "script": decider, "timeout": 8,
         "matcher": "Bash", "exec": True, "decision": True},
    ])
    try:
        p = _run_cli('{"tool_name":"Bash"}')
        obj = json.loads(p.stdout.strip().splitlines()[-1])
        ctx = obj["hookSpecificOutput"]["additionalContext"]
        assert ctx == "FROM-DECIDER", f"expected no duplication, got {ctx!r}"
    finally:
        (HERE / "manifest.json").write_text(backup, encoding="utf-8")


def test_launch_failure_is_attested(tmp_path, monkeypatch):
    """P2 thread: a non-timeout exec launch failure must leave a receipt.

    An OSError starting the child (or a decode failure) used to leave rc_sink
    empty -> rc=None, no receipt: a disarmed blocking guard indistinguishable
    from a healthy quiet check. The LAUNCH-FAILED sentinel must attest it.
    """
    script = _write(tmp_path, "bad/guard.py", "import sys\nsys.exit(0)\n")
    mod = load_dispatch()

    def _boom(*_a, **_k):
        raise OSError("cannot spawn child")

    monkeypatch.setattr(mod.subprocess, "Popen", _boom)
    manifest = {
        "hooks_root": str(tmp_path),
        "events": {"PreToolUse": {"checks": [
            {"name": "bad", "script": script, "timeout": 5,
             "matcher": "Bash", "exec": True, "blocking_rc": True},
        ]}},
    }
    records: list = []
    cap = io.StringIO()
    old_err = sys.stderr
    sys.stderr = cap
    try:
        out = mod.run("PreToolUse", '{"tool_name":"Bash"}', manifest,
                      collect=records)
    finally:
        sys.stderr = old_err
    assert out is None
    assert not records, "a launch-failed check must be dropped, not collected"
    assert "status=launch-failed" in cap.getvalue(), (
        f"the non-timeout launch failure must be attested: {cap.getvalue()!r}"
    )


def _pid_alive(pid: int) -> bool:
    """Liveness probe without killing: tasklist on Windows, kill(0) on POSIX."""
    if os.name == "nt":
        try:
            out = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True, text=True, timeout=10,
            ).stdout
        except Exception:
            return True  # cannot tell -> do not claim the kill succeeded
        return str(pid) in out
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def test_timed_out_exec_tree_is_killed(tmp_path):
    """P1 thread: a timed-out exec guard's CHILDREN must die with it.

    The old ``subprocess.run`` timeout killed only the leaf python.exe, so a
    hung guard's grandchild survived as an orphan and repeated calls
    accumulated processes. The dispatcher must TREE-kill before returning.
    """
    pidfile = tmp_path / "grandchild.pid"
    guard = _write(tmp_path, "hung/guard.py",
        "import subprocess, sys, time\n"
        "subprocess.Popen([sys.executable, '-c',\n"
        "    'import os, sys, time;'\n"
        "    'open(sys.argv[1], \"w\").write(str(os.getpid()));'\n"
        "    'time.sleep(60)', sys.argv[1]])\n"
        "time.sleep(60)\n")
    backup = _swap_manifest(tmp_path, [
        {"name": "hung", "script": guard, "args": [str(pidfile)],
         "timeout": 2, "matcher": "Bash", "exec": True, "blocking_rc": True},
    ])
    try:
        p = _run_cli('{"tool_name":"Bash"}')
        assert p.returncode == 0, "a timed-out exec check must fail open"
        assert "timeout" in p.stderr
        # The grandchild must have started (its pidfile) before the kill.
        deadline = time.monotonic() + 5
        while not pidfile.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert pidfile.exists(), "guard never spawned its grandchild (fixture)"
        gc_pid = int(pidfile.read_text(encoding="utf-8").strip())
        # Tree-kill is synchronous before the dispatcher exits, but /F cleanup
        # can lag a beat on Windows; poll briefly before declaring failure.
        deadline = time.monotonic() + 10
        while _pid_alive(gc_pid) and time.monotonic() < deadline:
            time.sleep(0.1)
        assert not _pid_alive(gc_pid), (
            f"grandchild pid {gc_pid} survived the dispatcher — tree-kill "
            "regressed to a leaf-only kill"
        )
    finally:
        (HERE / "manifest.json").write_text(backup, encoding="utf-8")
