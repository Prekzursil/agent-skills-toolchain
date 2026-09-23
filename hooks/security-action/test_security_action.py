#!/usr/bin/env python3
"""Tests for security-action/ledger.py and security-action/audit.py.

Run:
    python3 -m pytest hooks/security-action -q

Covers redaction, append persistence, atomic-replace hygiene, concurrent
writers (no lost/torn lines), and the audit.py PreToolUse hook end-to-end
(fail-open, opt-out, and authentic allow/block labelling via target-scope).
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import threading
import time
from pathlib import Path

import pytest

HOOK_DIR = Path(__file__).resolve().parent
LEDGER_PY = HOOK_DIR / "ledger.py"
AUDIT_PY = HOOK_DIR / "audit.py"
TARGET_SCOPE_DIR = HOOK_DIR.parent / "target-scope"


def _load_ledger():
    spec = importlib.util.spec_from_file_location("_sa_ledger", LEDGER_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def ledger(tmp_path):
    mod = _load_ledger()
    mod.ROOT = tmp_path / "root"
    return mod


# ---------------------------------------------------------------------------
# Redaction
# ---------------------------------------------------------------------------


class TestRedact:
    def test_secret_key_masked_wholesale(self, ledger):
        out = ledger.redact({"password": "hunter2", "api_key": "abc123"})
        assert out["password"] == "[REDACTED]"
        assert out["api_key"] == "[REDACTED]"

    def test_camel_and_dash_key_variants(self, ledger):
        out = ledger.redact({"apiKey": "x", "access-key": "y", "Authorization": "z"})
        assert out["apiKey"] == "[REDACTED]"
        assert out["access-key"] == "[REDACTED]"
        assert out["Authorization"] == "[REDACTED]"

    def test_non_secret_preserved(self, ledger):
        out = ledger.redact({"host": "api.example.com", "count": 3, "ok": True})
        assert out == {"host": "api.example.com", "count": 3, "ok": True}

    def test_value_pattern_aws_key(self, ledger):
        out = ledger.redact({"note": "id AKIA1234567890ABCDEF here"})
        assert "AKIA1234567890ABCDEF" not in out["note"]
        assert "[REDACTED]" in out["note"]

    def test_value_pattern_sk_token(self, ledger):
        out = ledger.redact("token sk-abcdef0123456789ABCDEFhij")
        assert "sk-abcdef0123456789ABCDEFhij" not in out
        assert "[REDACTED]" in out

    def test_url_query_token_redacted_host_kept(self, ledger):
        out = ledger.redact({"url": "https://example.com/?token=abcdefghijklmnop"})
        assert "abcdefghijklmnop" not in out["url"]
        assert "example.com" in out["url"]

    def test_jwt_redacted(self, ledger):
        jwt = "eyJhbGciZm.eyJzdWIiZm.SflKxwRJSMZ"
        out = ledger.redact({"h": f"Bearer {jwt}"})
        assert jwt not in out["h"]
        assert "[REDACTED]" in out["h"]

    def test_nested_list_and_dict(self, ledger):
        out = ledger.redact({"args": [{"secret": "s"}, {"host": "h"}]})
        assert out["args"][0]["secret"] == "[REDACTED]"
        assert out["args"][1]["host"] == "h"

    def test_private_key_block(self, ledger):
        pem = (
            "-----BEGIN RSA PRIVATE KEY-----\nMIIBjunk==\n-----END RSA PRIVATE KEY-----"
        )
        out = ledger.redact(pem)
        assert "MIIBjunk" not in out
        assert "[REDACTED]" in out


# ---------------------------------------------------------------------------
# Append + read
# ---------------------------------------------------------------------------


class TestAppend:
    def test_append_persists_and_reads_back(self, ledger):
        rec = ledger.append_record(
            {"tool": "WebFetch", "decision": "allow", "reason": "ok"},
            project_path="/proj",
        )
        assert rec["_written"] is True
        rows = ledger.read_records("/proj")
        assert len(rows) == 1
        assert rows[0]["tool"] == "WebFetch"
        assert rows[0]["decision"] == "allow"

    def test_append_adds_timestamp(self, ledger):
        ledger.append_record({"tool": "Bash"}, project_path="/proj")
        rows = ledger.read_records("/proj")
        assert "ts" in rows[0] and rows[0]["ts"]

    def test_append_redacts_args(self, ledger):
        ledger.append_record(
            {"tool": "Bash", "args": {"token": "supersecretvalue"}},
            project_path="/proj",
        )
        raw = ledger.actions_file("/proj").read_text(encoding="utf-8")
        assert "supersecretvalue" not in raw
        assert "[REDACTED]" in raw

    def test_append_only_never_rewrites_history(self, ledger):
        ledger.append_record({"tool": "A"}, project_path="/proj")
        ledger.append_record({"tool": "B"}, project_path="/proj")
        rows = ledger.read_records("/proj")
        assert [r["tool"] for r in rows] == ["A", "B"]

    def test_per_project_isolation(self, ledger):
        ledger.append_record({"tool": "A"}, project_path="/projA")
        ledger.append_record({"tool": "B"}, project_path="/projB")
        assert len(ledger.read_records("/projA")) == 1
        assert len(ledger.read_records("/projB")) == 1

    def test_read_empty_when_absent(self, ledger):
        assert ledger.read_records("/nope") == []


# ---------------------------------------------------------------------------
# Atomic replace hygiene
# ---------------------------------------------------------------------------


class TestAtomic:
    def test_no_tmp_or_lock_leftovers(self, ledger):
        ledger.append_record({"tool": "A"}, project_path="/proj")
        ledger.append_record({"tool": "B"}, project_path="/proj")
        d = ledger.actions_file("/proj").parent
        leftovers = [p.name for p in d.iterdir() if p.name != "actions.jsonl"]
        assert leftovers == [], f"unexpected leftovers: {leftovers}"

    def test_every_line_is_valid_json(self, ledger):
        for i in range(5):
            ledger.append_record({"tool": f"T{i}"}, project_path="/proj")
        raw = ledger.actions_file("/proj").read_text(encoding="utf-8")
        lines = [ln for ln in raw.splitlines() if ln.strip()]
        assert len(lines) == 5
        for ln in lines:
            json.loads(ln)  # must not raise


# ---------------------------------------------------------------------------
# Concurrency — no lost or torn lines under parallel appenders
# ---------------------------------------------------------------------------


class TestConcurrent:
    def test_concurrent_appends_all_land(self, ledger):
        n_threads = 8
        per_thread = 25
        expected = n_threads * per_thread

        def worker(tid: int):
            for j in range(per_thread):
                ledger.append_record(
                    {"tool": "C", "tid": tid, "j": j}, project_path="/proj"
                )

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        raw = ledger.actions_file("/proj").read_text(encoding="utf-8")
        lines = [ln for ln in raw.splitlines() if ln.strip()]
        # No lost writes.
        assert len(lines) == expected
        # No torn lines — every line parses, and every (tid, j) is present once.
        seen = set()
        for ln in lines:
            obj = json.loads(ln)
            seen.add((obj["tid"], obj["j"]))
        assert len(seen) == expected


# ---------------------------------------------------------------------------
# audit.py PreToolUse hook (end-to-end via subprocess)
# ---------------------------------------------------------------------------


def _run_audit(payload: str, root: Path, ts_dir: Path | None = None, extra_env=None):
    import subprocess

    env = os.environ.copy()
    env.pop("SECURITY_ACTION", None)
    env["SECURITY_ACTION_ROOT"] = str(root)
    if ts_dir is not None:
        env["TARGET_SCOPE_DIR"] = str(ts_dir)
    if extra_env:
        env.update(extra_env)
    r = subprocess.run(
        [sys.executable, str(AUDIT_PY)],
        input=payload,
        capture_output=True,
        text=True,
        env=env,
    )
    return r.returncode, r.stdout, r.stderr


def _write_ts_sidecar(ts_dir: Path, session: str, allow: list[str]):
    scopes = ts_dir / "scopes"
    scopes.mkdir(parents=True, exist_ok=True)
    (scopes / f"session-{session}.json").write_text(
        json.dumps(
            {
                "key": session,
                "key_type": "session",
                "allow": allow,
                "created_at": time.time(),
                "ttl_hours": 24.0,
            }
        ),
        encoding="utf-8",
    )


def _payload(tool, tool_input, session="s", cwd="/proj"):
    return json.dumps(
        {
            "tool_name": tool,
            "tool_input": tool_input,
            "session_id": session,
            "cwd": cwd,
        }
    )


class TestAuditHook:
    def _records(self, root: Path, cwd="/proj"):
        mod = _load_ledger()
        mod.ROOT = root
        return mod.read_records(cwd)

    def test_records_block_decision_from_target_scope(self, tmp_path):
        root = tmp_path / "root"
        ts_dir = tmp_path / "ts"
        _write_ts_sidecar(ts_dir, "s", ["*.example.com"])
        rc, _, _ = _run_audit(
            _payload("WebFetch", {"url": "https://evil.com/x"}, session="s"),
            root,
            ts_dir,
        )
        assert rc == 0  # audit never blocks
        rows = self._records(root)
        assert len(rows) == 1
        assert rows[0]["tool"] == "WebFetch"
        assert rows[0]["decision"] == "block"
        assert rows[0]["enforced"] is True

    def test_records_allow_decision_from_target_scope(self, tmp_path):
        root = tmp_path / "root"
        ts_dir = tmp_path / "ts"
        _write_ts_sidecar(ts_dir, "s", ["*.example.com"])
        rc, _, _ = _run_audit(
            _payload("WebFetch", {"url": "https://api.example.com/x"}, session="s"),
            root,
            ts_dir,
        )
        assert rc == 0
        rows = self._records(root)
        assert rows[0]["decision"] == "allow"

    def test_audit_redacts_secret_args(self, tmp_path):
        root = tmp_path / "root"
        ts_dir = tmp_path / "ts"
        _write_ts_sidecar(ts_dir, "s", ["*.example.com"])
        rc, _, _ = _run_audit(
            _payload(
                "Bash",
                {
                    "command": "curl https://api.example.com",
                    "headers": {"Authorization": "Bearer sk-topsecretvalue0123456789"},
                },
                session="s",
            ),
            root,
            ts_dir,
        )
        assert rc == 0
        mod = _load_ledger()
        mod.ROOT = root
        raw = mod.actions_file("/proj").read_text(encoding="utf-8")
        assert "sk-topsecretvalue0123456789" not in raw
        assert "[REDACTED]" in raw

    def test_audit_failopen_on_garbage_stdin(self, tmp_path):
        root = tmp_path / "root"
        rc, _, _ = _run_audit("NOT JSON", root, None)
        assert rc == 0

    def test_audit_optout_writes_nothing(self, tmp_path):
        root = tmp_path / "root"
        ts_dir = tmp_path / "ts"
        _write_ts_sidecar(ts_dir, "s", ["*.example.com"])
        rc, _, _ = _run_audit(
            _payload("WebFetch", {"url": "https://evil.com"}, session="s"),
            root,
            ts_dir,
            {"SECURITY_ACTION": "off"},
        )
        assert rc == 0
        assert self._records(root) == []

    def test_audit_records_even_without_sidecar(self, tmp_path):
        """No sidecar → not enforced, but the invocation is still audited."""
        root = tmp_path / "root"
        ts_dir = tmp_path / "ts"  # empty: no sidecar
        rc, _, _ = _run_audit(
            _payload("WebFetch", {"url": "https://evil.com"}, session="s"),
            root,
            ts_dir,
        )
        assert rc == 0
        rows = self._records(root)
        assert len(rows) == 1
        assert rows[0]["enforced"] is False
        assert rows[0]["decision"] == "allow"
