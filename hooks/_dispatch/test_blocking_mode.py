#!/usr/bin/env python3
"""Blocking-mode regression tests (2026-10-17 consolidation wave).

``exec`` checks must run as subprocesses whose REAL exit code, stderr and
decision JSON survive the dispatcher: an exit-2 block must make the dispatcher
itself exit 2 with the check's stderr; a deny decision JSON must be forwarded
verbatim; a hung exec check must fail open. If any of these break, the 7
consolidated PreToolUse guards are silently disarmed while looking healthy.

Run: pytest hooks/_dispatch/test_blocking_mode.py -q
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

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
