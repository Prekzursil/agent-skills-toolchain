#!/usr/bin/env python3
"""Tests for target-scope/check.py and target-scope/set_scope.py.

Run:
    python3 -m pytest hooks/target-scope -q

Subprocess-level tests reflect how the harness calls the hook (stdin JSON
payload, environment, exit code, stderr). Unit-level tests exercise the pure
extraction / matching / decision logic in _common.py directly.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

HOOK_DIR = Path(__file__).resolve().parent
CHECK_PY = HOOK_DIR / "check.py"
SET_SCOPE_PY = HOOK_DIR / "set_scope.py"
COMMON = HOOK_DIR / "_common.py"


# ---------------------------------------------------------------------------
# Subprocess helpers
# ---------------------------------------------------------------------------


def _run(script: Path, args=(), stdin: str = "", extra_env: dict | None = None):
    import subprocess

    env = os.environ.copy()
    env.pop("TARGET_SCOPE", None)
    env.pop("TARGET_SCOPE_AGENT", None)
    if extra_env:
        env.update(extra_env)
    r = subprocess.run(
        [sys.executable, str(script)] + list(args),
        input=stdin,
        capture_output=True,
        text=True,
        env=env,
    )
    return r.returncode, r.stdout, r.stderr


def _payload(tool: str, tool_input: dict, session_id="test-session", cwd="/proj") -> str:
    return json.dumps(
        {
            "tool_name": tool,
            "tool_input": tool_input,
            "session_id": session_id,
            "cwd": cwd,
        }
    )


def _check(payload: str, scope_dir=None, extra_env=None):
    env: dict = {}
    if scope_dir is not None:
        env["TARGET_SCOPE_DIR"] = scope_dir
    if extra_env:
        env.update(extra_env)
    return _run(CHECK_PY, stdin=payload, extra_env=env)


def _set(args, scope_dir=None):
    env: dict = {}
    if scope_dir is not None:
        env["TARGET_SCOPE_DIR"] = scope_dir
    return _run(SET_SCOPE_PY, args=args, extra_env=env)


# ---------------------------------------------------------------------------
# Unit tests — _common.py extraction + matching + evaluate
# ---------------------------------------------------------------------------


class TestCommon:
    @pytest.fixture(autouse=True)
    def _import(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location("_ts_common", COMMON)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.m = mod

    def _raws(self, tool_input):
        return {t["raw"] for t in self.m.extract_targets(tool_input)}

    # extraction --------------------------------------------------------------
    def test_extract_url_from_url_key(self):
        raws = self._raws({"url": "https://api.example.com/data"})
        assert "https://api.example.com/data" in raws

    def test_extract_url_yields_host_candidate(self):
        ts = self.m.extract_targets({"url": "https://api.example.com/data"})
        cands = ts[0]["candidates"]
        assert "api.example.com" in cands

    def test_extract_url_from_command_string(self):
        raws = self._raws({"command": "curl https://evil.com/x && echo done"})
        assert "https://evil.com/x" in raws

    def test_extract_host_key(self):
        ts = self.m.extract_targets({"host": "scanme.example.com"})
        assert ts and ts[0]["kind"] == "host"
        assert "scanme.example.com" in ts[0]["candidates"]

    def test_extract_host_key_strips_port(self):
        ts = self.m.extract_targets({"host": "scanme.example.com:8080"})
        assert "scanme.example.com" in ts[0]["candidates"]

    def test_extract_path_key(self):
        ts = self.m.extract_targets({"file_path": "/etc/passwd"})
        assert ts and ts[0]["kind"] == "path"

    def test_no_targets_from_innocent_keys(self):
        assert self._raws({"query": "how to write python", "count": 5}) == set()

    def test_nested_dict_walked(self):
        raws = self._raws({"options": {"endpoint": "https://n.example.com/v1"}})
        assert "https://n.example.com/v1" in raws

    # matching ----------------------------------------------------------------
    def test_host_glob_matches_subdomain(self):
        assert self.m.matches_any("api.example.com", ["*.example.com"])

    def test_host_glob_does_not_cross_dot_wrongly(self):
        assert not self.m.matches_any("evil.com", ["*.example.com"])

    def test_url_prefix_glob(self):
        assert self.m.matches_any(
            "https://api.example.com/v1/x", ["https://api.example.com/v1/**"]
        )

    def test_path_glob_tail(self):
        assert self.m.matches_any("/etc/passwd", ["/etc/**"])

    # evaluate ----------------------------------------------------------------
    def test_evaluate_no_sidecar_failopen(self, tmp_path):
        sd = tmp_path / "scopes"
        v = self.m.evaluate(
            {"tool_name": "WebFetch", "tool_input": {"url": "https://evil.com"}}, sd
        )
        assert v["enforced"] is False and v["decision"] == "allow"

    def test_evaluate_block_when_unmatched(self, tmp_path):
        sd = tmp_path / "scopes"
        self.m.write_sidecar(
            self.m.sidecar_path(sd, "session", "s"),
            "s",
            "session",
            ["*.example.com"],
        )
        v = self.m.evaluate(
            {
                "tool_name": "WebFetch",
                "tool_input": {"url": "https://evil.com"},
                "session_id": "s",
            },
            sd,
        )
        assert v["enforced"] and v["decision"] == "block"
        assert "evil.com" in " ".join(v["unmatched"])

    def test_evaluate_allow_when_matched(self, tmp_path):
        sd = tmp_path / "scopes"
        self.m.write_sidecar(
            self.m.sidecar_path(sd, "session", "s"),
            "s",
            "session",
            ["*.example.com"],
        )
        v = self.m.evaluate(
            {
                "tool_name": "WebFetch",
                "tool_input": {"url": "https://api.example.com/x"},
                "session_id": "s",
            },
            sd,
        )
        assert v["enforced"] and v["decision"] == "allow"

    def test_evaluate_no_targets_not_enforced(self, tmp_path):
        sd = tmp_path / "scopes"
        self.m.write_sidecar(
            self.m.sidecar_path(sd, "session", "s"), "s", "session", []
        )
        v = self.m.evaluate(
            {
                "tool_name": "WebSearch",
                "tool_input": {"query": "hello"},
                "session_id": "s",
            },
            sd,
        )
        assert v["enforced"] is False and v["decision"] == "allow"


# ---------------------------------------------------------------------------
# Integration: no sidecar → fail-open
# ---------------------------------------------------------------------------


class TestNoSidecar:
    def test_url_unrestricted(self, tmp_path):
        rc, _, _ = _check(
            _payload("WebFetch", {"url": "https://anything.example.org"}),
            scope_dir=str(tmp_path),
        )
        assert rc == 0

    def test_command_unrestricted(self, tmp_path):
        rc, _, _ = _check(
            _payload("Bash", {"command": "curl https://evil.com"}),
            scope_dir=str(tmp_path),
        )
        assert rc == 0


# ---------------------------------------------------------------------------
# Integration: in-scope → allowed
# ---------------------------------------------------------------------------


class TestInScope:
    def test_host_glob_allows(self, tmp_path):
        _set(["--session", "s1", "--allow", "*.example.com"], str(tmp_path))
        rc, _, _ = _check(
            _payload("WebFetch", {"url": "https://api.example.com/x"}, session_id="s1"),
            str(tmp_path),
        )
        assert rc == 0

    def test_exact_host_allows_any_url_on_it(self, tmp_path):
        _set(["--session", "s2", "--allow", "api.example.com"], str(tmp_path))
        rc, _, _ = _check(
            _payload(
                "Bash",
                {"command": "curl https://api.example.com/deep/path?x=1"},
                session_id="s2",
            ),
            str(tmp_path),
        )
        assert rc == 0

    def test_url_prefix_allows(self, tmp_path):
        _set(
            ["--session", "s3", "--allow", "https://api.example.com/v1/**"],
            str(tmp_path),
        )
        rc, _, _ = _check(
            _payload(
                "WebFetch", {"url": "https://api.example.com/v1/users"}, session_id="s3"
            ),
            str(tmp_path),
        )
        assert rc == 0

    def test_path_glob_allows(self, tmp_path):
        _set(["--session", "s4", "--allow", "/tmp/**"], str(tmp_path))
        rc, _, _ = _check(
            _payload("Bash", {"file_path": "/tmp/work/out.txt"}, session_id="s4"),
            str(tmp_path),
        )
        assert rc == 0

    def test_multiple_allow_patterns(self, tmp_path):
        _set(
            ["--session", "s5", "--allow", "*.example.com", "--allow", "/tmp/**"],
            str(tmp_path),
        )
        rc, _, _ = _check(
            _payload("Bash", {"host": "db.example.com"}, session_id="s5"),
            str(tmp_path),
        )
        assert rc == 0


# ---------------------------------------------------------------------------
# Integration: out-of-scope → blocked
# ---------------------------------------------------------------------------


class TestOutOfScope:
    def test_wrong_host_blocked(self, tmp_path):
        _set(["--session", "b1", "--allow", "*.example.com"], str(tmp_path))
        rc, _, err = _check(
            _payload("WebFetch", {"url": "https://evil.com/x"}, session_id="b1"),
            str(tmp_path),
        )
        assert rc == 2
        assert "out of declared target scope" in err.lower()

    def test_block_message_names_target(self, tmp_path):
        _set(["--session", "b2", "--allow", "*.example.com"], str(tmp_path))
        rc, _, err = _check(
            _payload("Bash", {"command": "curl https://evil.com"}, session_id="b2"),
            str(tmp_path),
        )
        assert rc == 2
        assert "evil.com" in err

    def test_block_message_lists_allowed(self, tmp_path):
        _set(["--session", "b3", "--allow", "*.example.com"], str(tmp_path))
        rc, _, err = _check(
            _payload("WebFetch", {"url": "https://evil.com"}, session_id="b3"),
            str(tmp_path),
        )
        assert rc == 2
        assert "*.example.com" in err

    def test_path_out_of_scope_blocked(self, tmp_path):
        _set(["--session", "b4", "--allow", "/tmp/**"], str(tmp_path))
        rc, _, _ = _check(
            _payload("Bash", {"file_path": "/etc/passwd"}, session_id="b4"),
            str(tmp_path),
        )
        assert rc == 2

    def test_empty_allow_blocks_all_targets(self, tmp_path):
        _set(["--session", "b5"], str(tmp_path))  # no --allow → empty allow-list
        rc, _, _ = _check(
            _payload("WebFetch", {"url": "https://api.example.com"}, session_id="b5"),
            str(tmp_path),
        )
        assert rc == 2

    def test_one_bad_target_among_many_blocks(self, tmp_path):
        _set(["--session", "b6", "--allow", "*.example.com"], str(tmp_path))
        rc, _, _ = _check(
            _payload(
                "Bash",
                {"command": "curl https://api.example.com && curl https://evil.com"},
                session_id="b6",
            ),
            str(tmp_path),
        )
        assert rc == 2


# ---------------------------------------------------------------------------
# No targets → fail-open even with a restrictive sidecar
# ---------------------------------------------------------------------------


class TestNoTargets:
    def test_no_target_args_failopen(self, tmp_path):
        _set(["--session", "n1"], str(tmp_path))  # empty allow-list (block-all)
        rc, _, _ = _check(
            _payload("WebSearch", {"query": "python tips"}, session_id="n1"),
            str(tmp_path),
        )
        assert rc == 0  # nothing target-like to check → allowed


# ---------------------------------------------------------------------------
# Malformed sidecar / garbage stdin → fail-open
# ---------------------------------------------------------------------------


class TestMalformed:
    def _sidecar(self, tmp_path, sid, content):
        d = tmp_path / "scopes"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"session-{sid}.json").write_text(content, encoding="utf-8")

    def test_bad_json_failopen(self, tmp_path):
        self._sidecar(tmp_path, "bad", "not json at all")
        rc, _, _ = _check(
            _payload("WebFetch", {"url": "https://evil.com"}, session_id="bad"),
            str(tmp_path),
        )
        assert rc == 0

    def test_allow_not_list_failopen(self, tmp_path):
        self._sidecar(tmp_path, "bad2", json.dumps({"allow": "nope"}))
        rc, _, _ = _check(
            _payload("WebFetch", {"url": "https://evil.com"}, session_id="bad2"),
            str(tmp_path),
        )
        assert rc == 0

    def test_garbage_stdin_failopen(self, tmp_path):
        rc, _, _ = _run(
            CHECK_PY, stdin="NOT JSON", extra_env={"TARGET_SCOPE_DIR": str(tmp_path)}
        )
        assert rc == 0

    def test_empty_payload_failopen(self):
        rc, _, _ = _check("{}")
        assert rc == 0


# ---------------------------------------------------------------------------
# Opt-out
# ---------------------------------------------------------------------------


class TestOptOut:
    def test_env_off(self, tmp_path):
        _set(["--session", "o1", "--allow", "*.example.com"], str(tmp_path))
        rc, _, _ = _check(
            _payload("WebFetch", {"url": "https://evil.com"}, session_id="o1"),
            str(tmp_path),
            {"TARGET_SCOPE": "off"},
        )
        assert rc == 0

    def test_env_zero(self, tmp_path):
        _set(["--session", "o2", "--allow", "*.example.com"], str(tmp_path))
        rc, _, _ = _check(
            _payload("WebFetch", {"url": "https://evil.com"}, session_id="o2"),
            str(tmp_path),
            {"TARGET_SCOPE": "0"},
        )
        assert rc == 0

    def test_disabled_file(self, tmp_path):
        _set(["--session", "o3", "--allow", "*.example.com"], str(tmp_path))
        disabled = HOOK_DIR / ".disabled"
        disabled.write_text("", encoding="utf-8")
        try:
            rc, _, _ = _check(
                _payload("WebFetch", {"url": "https://evil.com"}, session_id="o3"),
                str(tmp_path),
            )
            assert rc == 0
        finally:
            disabled.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Agent-name keying (isolation-safe path)
# ---------------------------------------------------------------------------


class TestAgentKeying:
    def test_agent_allows_in_scope(self, tmp_path):
        _set(["--agent-name", "scan-1", "--allow", "*.example.com"], str(tmp_path))
        rc, _, _ = _check(
            _payload("WebFetch", {"url": "https://api.example.com"}),
            str(tmp_path),
            {"TARGET_SCOPE_AGENT": "scan-1"},
        )
        assert rc == 0

    def test_agent_blocks_out_of_scope(self, tmp_path):
        _set(["--agent-name", "scan-2", "--allow", "*.example.com"], str(tmp_path))
        rc, _, _ = _check(
            _payload("WebFetch", {"url": "https://evil.com"}),
            str(tmp_path),
            {"TARGET_SCOPE_AGENT": "scan-2"},
        )
        assert rc == 2

    def test_agent_takes_precedence_over_session(self, tmp_path):
        _set(["--session", "sess", "--allow", "*.example.com"], str(tmp_path))
        _set(["--agent-name", "strict", "--allow", "only.example.com"], str(tmp_path))
        rc, _, _ = _check(
            _payload("WebFetch", {"url": "https://api.example.com"}, session_id="sess"),
            str(tmp_path),
            {"TARGET_SCOPE_AGENT": "strict"},
        )
        assert rc == 2  # narrower agent scope wins


# ---------------------------------------------------------------------------
# set_scope.py
# ---------------------------------------------------------------------------


class TestSetScope:
    def test_writes_session_sidecar(self, tmp_path):
        rc, out, _ = _set(
            ["--session", "w1", "--allow", "*.example.com", "--allow", "/tmp/**"],
            str(tmp_path),
        )
        assert rc == 0
        sidecar = tmp_path / "scopes" / "session-w1.json"
        assert sidecar.exists()
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        assert "*.example.com" in data["allow"]
        assert "SUCCESS" in out

    def test_clear(self, tmp_path):
        _set(["--session", "w2", "--allow", "*.example.com"], str(tmp_path))
        rc, out, _ = _set(["--session", "w2", "--clear"], str(tmp_path))
        assert rc == 0
        assert not (tmp_path / "scopes" / "session-w2.json").exists()
        assert "SUCCESS" in out

    def test_list(self, tmp_path):
        _set(["--session", "w3", "--allow", "*.example.com"], str(tmp_path))
        rc, out, _ = _set(["--list"], str(tmp_path))
        assert rc == 0
        assert "SUCCESS:list count=1" in out
        assert "w3" in out

    def test_gc_removes_expired(self, tmp_path):
        import time

        scopes = tmp_path / "scopes"
        scopes.mkdir(parents=True, exist_ok=True)
        old = {
            "key": "old",
            "key_type": "session",
            "allow": [],
            "created_at": time.time() - 100_000,
            "ttl_hours": 1.0,
        }
        (scopes / "session-old.json").write_text(json.dumps(old), encoding="utf-8")
        rc, _, _ = _set(["--gc"], str(tmp_path))
        assert rc == 0
        assert not (scopes / "session-old.json").exists()

    def test_no_key_errors(self):
        rc, _, err = _set(["--allow", "*.example.com"])
        assert rc != 0 or err
