#!/usr/bin/env python3
"""Tests for file-scope/check.py and file-scope/set_scope.py.

Run:
    pytest C:/Users/Prekzursil/.claude/hooks/file-scope/test_file_scope.py -v

All subprocess-level tests reflect how Claude Code actually calls the hook
(stdin JSON payload, environment, exit code, stderr).  Unit-level tests cover
the core glob / path-matching logic in _common.py directly.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

import pytest

HOOK_DIR = Path(__file__).resolve().parent
CHECK_PY = HOOK_DIR / "check.py"
SET_SCOPE_PY = HOOK_DIR / "set_scope.py"
COMMON = HOOK_DIR / "_common.py"


# ---------------------------------------------------------------------------
# Subprocess helpers
# ---------------------------------------------------------------------------


def _run(
    script: Path, args: list[str] = (), stdin: str = "", extra_env: dict | None = None
):
    """Run a Python script, return (rc, stdout, stderr)."""
    import subprocess

    env = os.environ.copy()
    # Always clear opt-out vars from the parent environment so tests start clean.
    env.pop("FILE_SCOPE", None)
    env.pop("FILE_SCOPE_AGENT", None)
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


def _payload(
    tool: str, file_path: str, session_id: str = "test-session", cwd: str = "C:/project"
) -> str:
    return json.dumps(
        {
            "tool_name": tool,
            "tool_input": {"file_path": file_path},
            "session_id": session_id,
            "cwd": cwd,
        }
    )


def _nb_payload(
    notebook_path: str, session_id: str = "test-session", cwd: str = "C:/project"
) -> str:
    return json.dumps(
        {
            "tool_name": "NotebookEdit",
            "tool_input": {"notebook_path": notebook_path},
            "session_id": session_id,
            "cwd": cwd,
        }
    )


def _check(
    payload: str, scope_dir: str | None = None, extra_env: dict | None = None
) -> tuple[int, str, str]:
    env: dict = {}
    if scope_dir is not None:
        env["FILE_SCOPE_DIR"] = scope_dir
    if extra_env:
        env.update(extra_env)
    return _run(CHECK_PY, stdin=payload, extra_env=env)


def _set(args: list[str], scope_dir: str | None = None) -> tuple[int, str, str]:
    env: dict = {}
    if scope_dir is not None:
        env["FILE_SCOPE_DIR"] = scope_dir
    return _run(SET_SCOPE_PY, args=args, extra_env=env)


# ---------------------------------------------------------------------------
# Unit tests — _common.py matching logic
# ---------------------------------------------------------------------------


class TestGlobMatching:
    """Import _common directly for fast unit coverage of the match engine."""

    @pytest.fixture(autouse=True)
    def _import(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location("_common", COMMON)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.m = mod

    def _match(self, path: str, *patterns: str) -> bool:
        return self.m.matches_any(path, list(patterns))

    # ** patterns
    def test_double_star_matches_nested(self):
        assert self._match("src/foo/bar.py", "src/**/*.py")

    def test_double_star_matches_root_level(self):
        """src/**/*.py should match src/bar.py (zero intermediate dirs)."""
        assert self._match("src/bar.py", "src/**/*.py")

    def test_double_star_tail_matches_abs_path(self):
        assert self._match("C:/project/src/foo/bar.py", "src/**/*.py")

    def test_double_star_trailing_matches_any_depth(self):
        assert self._match("tests/a/b/c/foo.py", "tests/**")

    def test_double_star_trailing_matches_shallow(self):
        assert self._match("tests/foo.py", "tests/**")

    # * within a component — no slash crossing
    def test_single_star_within_component(self):
        assert self._match("src/test_foo.py", "src/test_*.py")

    def test_single_star_does_not_cross_slash(self):
        """src/test_*.py must NOT match src/test_foo/bar.py."""
        assert not self._match("src/test_foo/bar.py", "src/test_*.py")

    # Absolute patterns
    def test_absolute_pattern_direct_match(self):
        assert self._match("C:/project/src/foo.py", "C:/project/src/**")

    def test_absolute_pattern_not_matched_by_tail(self):
        """An absolute pattern must match the full path, not a tail."""
        assert not self._match("C:/other/src/foo.py", "C:/project/src/**")

    # Backslash normalization
    def test_backslash_path_normalized(self):
        assert self._match("C:\\project\\src\\foo.py", "src/**/*.py")

    def test_backslash_pattern_normalized(self):
        assert self._match("src/foo.py", "src\\**\\*.py")

    # Exact filename
    def test_exact_filename(self):
        assert self._match("C:/project/CHANGELOG.md", "CHANGELOG.md")

    # No match
    def test_wrong_dir_not_matched(self):
        assert not self._match("vendor/foo.py", "src/**/*.py")

    def test_empty_patterns_no_match(self):
        assert not self._match("src/foo.py", *[])

    # Windows case-folding (H1)
    @pytest.mark.skipif(
        os.name != "nt", reason="Windows drive-letter case-folding only"
    )
    def test_windows_case_fold_abs_pattern_lower_path(self):
        """H1: uppercase pattern must match lowercase drive-letter path."""
        assert self._match("c:/p/src/x.py", "C:/p/src/**")

    @pytest.mark.skipif(
        os.name != "nt", reason="Windows drive-letter case-folding only"
    )
    def test_windows_case_fold_abs_pattern_upper_path(self):
        """H1: lowercase pattern must match uppercase drive-letter path."""
        assert self._match("C:/P/SRC/x.py", "c:/p/src/**")

    @pytest.mark.skipif(
        os.name != "nt", reason="Windows drive-letter case-folding only"
    )
    def test_windows_case_fold_does_not_break_mismatch(self):
        """H1: case-folding must not make different dirs match each other."""
        assert not self._match("c:/other/src/foo.py", "C:/project/src/**")


# ---------------------------------------------------------------------------
# Integration: no sidecar → fail-open
# ---------------------------------------------------------------------------


class TestNoSidecar:
    def test_write_unrestricted(self, tmp_path):
        rc, _, _ = _check(
            _payload("Write", "C:/project/anything.py"), scope_dir=str(tmp_path)
        )
        assert rc == 0

    def test_edit_unrestricted(self, tmp_path):
        rc, _, _ = _check(
            _payload("Edit", "C:/project/secret.py"), scope_dir=str(tmp_path)
        )
        assert rc == 0

    def test_multiedit_unrestricted(self, tmp_path):
        p = json.dumps(
            {
                "tool_name": "MultiEdit",
                "tool_input": {"file_path": "C:/project/foo.py"},
                "session_id": "s",
                "cwd": "C:/project",
            }
        )
        rc, _, _ = _check(p, scope_dir=str(tmp_path))
        assert rc == 0


# ---------------------------------------------------------------------------
# Integration: in-scope → allowed
# ---------------------------------------------------------------------------


class TestInScope:
    def test_simple_glob(self, tmp_path):
        _set(["--session", "s1", "--allow", "src/**/*.py"], str(tmp_path))
        rc, _, _ = _check(
            _payload("Edit", "C:/project/src/feature/foo.py", session_id="s1"),
            str(tmp_path),
        )
        assert rc == 0

    def test_root_level_file_under_double_star(self, tmp_path):
        """src/**/*.py should allow src/bar.py (zero intermediate dirs)."""
        _set(["--session", "s2", "--allow", "src/**/*.py"], str(tmp_path))
        rc, _, _ = _check(
            _payload("Write", "C:/project/src/bar.py", session_id="s2"), str(tmp_path)
        )
        assert rc == 0

    def test_trailing_double_star(self, tmp_path):
        _set(["--session", "s3", "--allow", "tests/**"], str(tmp_path))
        rc, _, _ = _check(
            _payload("Write", "C:/project/tests/unit/test_foo.py", session_id="s3"),
            str(tmp_path),
        )
        assert rc == 0

    def test_multiple_allow_patterns(self, tmp_path):
        _set(
            ["--session", "s4", "--allow", "src/**", "--allow", "tests/**"],
            str(tmp_path),
        )
        rc, _, _ = _check(
            _payload("Write", "C:/project/tests/test_x.py", session_id="s4"),
            str(tmp_path),
        )
        assert rc == 0

    def test_exact_filename(self, tmp_path):
        _set(["--session", "s5", "--allow", "CHANGELOG.md"], str(tmp_path))
        rc, _, _ = _check(
            _payload("Write", "C:/project/CHANGELOG.md", session_id="s5"), str(tmp_path)
        )
        assert rc == 0

    def test_windows_backslash_path(self, tmp_path):
        _set(["--session", "s6", "--allow", "src/**/*.py"], str(tmp_path))
        p = json.dumps(
            {
                "tool_name": "Write",
                "tool_input": {"file_path": "C:\\project\\src\\module\\foo.py"},
                "session_id": "s6",
                "cwd": "C:\\project",
            }
        )
        rc, _, _ = _check(p, str(tmp_path))
        assert rc == 0

    def test_absolute_pattern_match(self, tmp_path):
        _set(["--session", "s7", "--allow", "C:/project/src/**"], str(tmp_path))
        rc, _, _ = _check(
            _payload("Edit", "C:/project/src/x.py", session_id="s7"), str(tmp_path)
        )
        assert rc == 0

    def test_relative_file_path_resolved_against_cwd(self, tmp_path):
        _set(["--session", "s8", "--allow", "src/**/*.py"], str(tmp_path))
        p = json.dumps(
            {
                "tool_name": "Edit",
                "tool_input": {"file_path": "src/foo.py"},  # relative
                "session_id": "s8",
                "cwd": "C:/project",
            }
        )
        rc, _, _ = _check(p, str(tmp_path))
        assert rc == 0

    @pytest.mark.skipif(
        os.name != "nt", reason="Windows drive-letter case-folding only"
    )
    def test_windows_abs_case_mismatch_allowed(self, tmp_path):
        """H1: allow 'C:/p/src/**'; write path 'c:/p/src/x.py' → rc=0 on Windows.

        This is the exact scenario from the adversarial review: sidecar stores
        uppercase 'C:' in the pattern but Claude Code reports the file path with
        lowercase 'c:'.  Before the fix this wrongly returned rc=2 (blocked).
        """
        _set(["--session", "wincm1", "--allow", "C:/p/src/**"], str(tmp_path))
        rc, _, _ = _check(
            _payload("Write", "c:/p/src/x.py", session_id="wincm1", cwd="C:/p"),
            str(tmp_path),
        )
        assert rc == 0  # must be ALLOWED, not blocked


# ---------------------------------------------------------------------------
# Integration: out-of-scope → blocked
# ---------------------------------------------------------------------------


class TestOutOfScope:
    def test_wrong_directory_blocked(self, tmp_path):
        _set(["--session", "b1", "--allow", "src/**/*.py"], str(tmp_path))
        rc, _, err = _check(
            _payload("Edit", "C:/project/tests/test_foo.py", session_id="b1"),
            str(tmp_path),
        )
        assert rc == 2
        assert "out of declared file scope" in err.lower()

    def test_block_message_contains_attempted_path(self, tmp_path):
        _set(["--session", "b2", "--allow", "src/**"], str(tmp_path))
        rc, _, err = _check(
            _payload("Write", "C:/project/lib/foo.py", session_id="b2"), str(tmp_path)
        )
        assert rc == 2
        assert "lib/foo.py" in err or "C:/project/lib/foo.py" in err

    def test_block_message_contains_allowed_globs(self, tmp_path):
        _set(
            ["--session", "b3", "--allow", "src/**", "--allow", "docs/**"],
            str(tmp_path),
        )
        rc, _, err = _check(
            _payload("Write", "C:/project/config.yaml", session_id="b3"), str(tmp_path)
        )
        assert rc == 2
        assert "src/**" in err

    def test_multiedit_blocked(self, tmp_path):
        _set(["--session", "b4", "--allow", "src/**"], str(tmp_path))
        p = json.dumps(
            {
                "tool_name": "MultiEdit",
                "tool_input": {"file_path": "C:/project/vendor/foo.py"},
                "session_id": "b4",
                "cwd": "C:/project",
            }
        )
        rc, _, _ = _check(p, str(tmp_path))
        assert rc == 2

    def test_notebookedit_blocked(self, tmp_path):
        _set(["--session", "b5", "--allow", "notebooks/**"], str(tmp_path))
        rc, _, _ = _check(
            _nb_payload("C:/project/src/analysis.ipynb", session_id="b5"), str(tmp_path)
        )
        assert rc == 2

    def test_empty_allow_list_blocks_all_writes(self, tmp_path):
        """Explicit empty allowlist → block every write (read-only agent)."""
        _set(["--session", "b6"], str(tmp_path))  # no --allow args
        rc, _, _ = _check(
            _payload("Write", "C:/project/anything.py", session_id="b6"), str(tmp_path)
        )
        assert rc == 2

    def test_nested_wrong_sibling_blocked(self, tmp_path):
        _set(["--session", "b7", "--allow", "src/feature_a/**"], str(tmp_path))
        rc, _, _ = _check(
            _payload("Edit", "C:/project/src/feature_b/impl.py", session_id="b7"),
            str(tmp_path),
        )
        assert rc == 2

    def test_single_star_does_not_cross_directory(self, tmp_path):
        """src/test_*.py must NOT match src/test_dir/bar.py."""
        _set(["--session", "b8", "--allow", "src/test_*.py"], str(tmp_path))
        rc, _, _ = _check(
            _payload("Edit", "C:/project/src/test_dir/bar.py", session_id="b8"),
            str(tmp_path),
        )
        assert rc == 2


# ---------------------------------------------------------------------------
# Malformed sidecar → fail-open
# ---------------------------------------------------------------------------


class TestMalformedSidecar:
    def _sidecar(self, tmp_path, sid: str, content: str):
        d = tmp_path / "scopes"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"session-{sid}.json").write_text(content, encoding="utf-8")

    def test_bad_json_allows(self, tmp_path):
        self._sidecar(tmp_path, "bad", "not json at all")
        rc, _, _ = _check(
            _payload("Edit", "C:/project/secret.py", session_id="bad"), str(tmp_path)
        )
        assert rc == 0

    def test_allow_not_a_list_allows(self, tmp_path):
        self._sidecar(tmp_path, "bad2", json.dumps({"allow": "not-a-list"}))
        rc, _, _ = _check(
            _payload("Edit", "C:/project/secret.py", session_id="bad2"), str(tmp_path)
        )
        assert rc == 0

    def test_empty_file_allows(self, tmp_path):
        self._sidecar(tmp_path, "empty", "")
        rc, _, _ = _check(
            _payload("Edit", "C:/project/secret.py", session_id="empty"), str(tmp_path)
        )
        assert rc == 0

    def test_missing_allow_key_allows(self, tmp_path):
        self._sidecar(tmp_path, "noallow", json.dumps({"other": "data"}))
        rc, _, _ = _check(
            _payload("Edit", "C:/project/secret.py", session_id="noallow"),
            str(tmp_path),
        )
        assert rc == 0


# ---------------------------------------------------------------------------
# Opt-out
# ---------------------------------------------------------------------------


class TestOptOut:
    def test_disabled_file_bypasses_block(self, tmp_path):
        _set(["--session", "s", "--allow", "src/**"], str(tmp_path))
        disabled = HOOK_DIR / ".disabled"
        disabled.write_text("", encoding="utf-8")
        try:
            rc, _, _ = _check(
                _payload("Edit", "C:/project/other.py", session_id="s"), str(tmp_path)
            )
            assert rc == 0
        finally:
            disabled.unlink(missing_ok=True)

    def test_env_off(self, tmp_path):
        _set(["--session", "s", "--allow", "src/**"], str(tmp_path))
        rc, _, _ = _check(
            _payload("Edit", "C:/project/other.py", session_id="s"),
            str(tmp_path),
            {"FILE_SCOPE": "off"},
        )
        assert rc == 0

    def test_env_zero(self, tmp_path):
        _set(["--session", "s", "--allow", "src/**"], str(tmp_path))
        rc, _, _ = _check(
            _payload("Edit", "C:/project/other.py", session_id="s"),
            str(tmp_path),
            {"FILE_SCOPE": "0"},
        )
        assert rc == 0

    def test_env_false(self, tmp_path):
        _set(["--session", "s", "--allow", "src/**"], str(tmp_path))
        rc, _, _ = _check(
            _payload("Edit", "C:/project/other.py", session_id="s"),
            str(tmp_path),
            {"FILE_SCOPE": "false"},
        )
        assert rc == 0


# ---------------------------------------------------------------------------
# set_scope.py
# ---------------------------------------------------------------------------


class TestSetScope:
    def test_writes_session_sidecar(self, tmp_path):
        rc, out, _ = _set(
            ["--session", "sess1", "--allow", "src/**/*.py", "--allow", "tests/**"],
            str(tmp_path),
        )
        assert rc == 0
        sidecar = tmp_path / "scopes" / "session-sess1.json"
        assert sidecar.exists()
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        assert "src/**/*.py" in data["allow"]
        assert "tests/**" in data["allow"]
        assert "created_at" in data
        assert "SUCCESS" in out

    def test_writes_agent_sidecar(self, tmp_path):
        rc, out, _ = _set(
            ["--agent-name", "coder-1", "--allow", "src/feature_a/**"], str(tmp_path)
        )
        assert rc == 0
        assert (tmp_path / "scopes" / "agent-coder-1.json").exists()
        assert "SUCCESS" in out

    def test_writes_cwd_sidecar(self, tmp_path):
        rc, out, _ = _set(
            ["--cwd", "C:/project/workspace", "--allow", "src/**"], str(tmp_path)
        )
        assert rc == 0
        # nosemgrep: python.lang.security.insecure-hash-algorithms.insecure-hash-algorithm-sha1 -- test mirrors the production non-cryptographic cwd-path slug, not a security control
        slug = hashlib.sha1("c:/project/workspace".encode()).hexdigest()[:12]
        assert (tmp_path / "scopes" / f"cwd-{slug}.json").exists()
        assert "SUCCESS" in out

    def test_clear_session(self, tmp_path):
        _set(["--session", "sess2", "--allow", "src/**"], str(tmp_path))
        sidecar = tmp_path / "scopes" / "session-sess2.json"
        assert sidecar.exists()
        rc, out, _ = _set(["--session", "sess2", "--clear"], str(tmp_path))
        assert rc == 0
        assert not sidecar.exists()
        assert "SUCCESS" in out

    def test_clear_nonexistent_ok(self, tmp_path):
        rc, out, _ = _set(["--session", "nosuch", "--clear"], str(tmp_path))
        assert rc == 0
        assert "SUCCESS" in out

    def test_second_write_replaces_sidecar(self, tmp_path):
        _set(["--session", "sess3", "--allow", "src/**"], str(tmp_path))
        _set(["--session", "sess3", "--allow", "tests/**"], str(tmp_path))
        data = json.loads(
            (tmp_path / "scopes" / "session-sess3.json").read_text(encoding="utf-8")
        )
        assert "tests/**" in data["allow"]
        assert "src/**" not in data["allow"]

    def test_gc_removes_expired(self, tmp_path):
        scopes = tmp_path / "scopes"
        scopes.mkdir(parents=True, exist_ok=True)
        old = {
            "key": "old",
            "key_type": "session",
            "allow": [],
            "created_at": time.time() - 100_000,
            "ttl_hours": 1.0,
        }
        fresh = {
            "key": "fresh",
            "key_type": "session",
            "allow": ["src/**"],
            "created_at": time.time(),
            "ttl_hours": 24.0,
        }
        (scopes / "session-old.json").write_text(json.dumps(old), encoding="utf-8")
        (scopes / "session-fresh.json").write_text(json.dumps(fresh), encoding="utf-8")
        rc, out, _ = _set(["--gc"], str(tmp_path))
        assert rc == 0
        assert not (scopes / "session-old.json").exists()
        assert (scopes / "session-fresh.json").exists()

    def test_no_key_errors_gracefully(self):
        """Calling set_scope.py without --session/--agent-name/--cwd exits non-zero."""
        rc, _, err = _set(["--allow", "src/**"])
        assert rc != 0 or err  # either error exit or stderr message

    def test_list_shows_active_sidecars(self, tmp_path):
        """--list reports active sidecars and a SUCCESS:list count= line."""
        _set(
            ["--session", "listme", "--allow", "src/**", "--allow", "tests/**"],
            str(tmp_path),
        )
        rc, out, _ = _set(["--list"], str(tmp_path))
        assert rc == 0
        assert "SUCCESS:list count=1" in out
        assert "listme" in out
        assert "src/**" in out

    def test_list_empty_directory(self, tmp_path):
        """--list on an empty scopes dir reports count=0."""
        rc, out, _ = _set(["--list"], str(tmp_path))
        assert rc == 0
        assert "SUCCESS:list count=0" in out

    def test_list_excludes_expired(self, tmp_path):
        """--list must not include expired sidecars."""
        scopes = tmp_path / "scopes"
        scopes.mkdir(parents=True, exist_ok=True)
        expired = {
            "key": "gone",
            "key_type": "session",
            "allow": ["x/**"],
            "created_at": time.time() - 100_000,
            "ttl_hours": 1.0,
        }
        (scopes / "session-gone.json").write_text(json.dumps(expired), encoding="utf-8")
        rc, out, _ = _set(["--list"], str(tmp_path))
        assert rc == 0
        assert "SUCCESS:list count=0" in out
        assert "gone" not in out


# ---------------------------------------------------------------------------
# Agent-name keying
# ---------------------------------------------------------------------------


class TestAgentNameKeying:
    def test_agent_name_sidecar_allows_in_scope(self, tmp_path):
        _set(["--agent-name", "coder-1", "--allow", "src/feature_a/**"], str(tmp_path))
        rc, _, _ = _check(
            _payload("Edit", "C:/project/src/feature_a/impl.py"),
            str(tmp_path),
            {"FILE_SCOPE_AGENT": "coder-1"},
        )
        assert rc == 0

    def test_agent_name_sidecar_blocks_out_of_scope(self, tmp_path):
        _set(["--agent-name", "coder-2", "--allow", "src/feature_b/**"], str(tmp_path))
        rc, _, _ = _check(
            _payload("Edit", "C:/project/src/feature_a/impl.py"),
            str(tmp_path),
            {"FILE_SCOPE_AGENT": "coder-2"},
        )
        assert rc == 2

    def test_agent_name_takes_precedence_over_session(self, tmp_path):
        """Agent-name sidecar is checked before session sidecar."""
        _set(["--session", "sess", "--allow", "src/**"], str(tmp_path))
        _set(["--agent-name", "strict", "--allow", "src/feature_a/**"], str(tmp_path))
        # The session sidecar allows src/feature_b/; the agent sidecar does not.
        rc, _, _ = _check(
            _payload("Edit", "C:/project/src/feature_b/foo.py", session_id="sess"),
            str(tmp_path),
            {"FILE_SCOPE_AGENT": "strict"},
        )
        assert rc == 2  # blocked by narrower agent scope

    def test_no_agent_env_falls_back_to_session(self, tmp_path):
        _set(["--session", "sess-fb", "--allow", "src/**"], str(tmp_path))
        rc, _, _ = _check(
            _payload("Edit", "C:/project/src/foo.py", session_id="sess-fb"),
            str(tmp_path),
        )
        assert rc == 0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_non_write_tool_skipped(self, tmp_path):
        """Read tool is not a write; check should skip it."""
        _set(["--session", "e1", "--allow", "src/**"], str(tmp_path))
        p = json.dumps(
            {
                "tool_name": "Read",
                "tool_input": {"file_path": "C:/project/secret.py"},
                "session_id": "e1",
                "cwd": "C:/project",
            }
        )
        rc, _, _ = _check(p, str(tmp_path))
        assert rc == 0

    def test_empty_payload_is_failopen(self):
        rc, _, _ = _check("{}")
        assert rc == 0

    def test_missing_file_path_is_failopen(self, tmp_path):
        _set(["--session", "e2", "--allow", "src/**"], str(tmp_path))
        p = json.dumps(
            {
                "tool_name": "Edit",
                "tool_input": {},
                "session_id": "e2",
                "cwd": "C:/project",
            }
        )
        rc, _, _ = _check(p, str(tmp_path))
        assert rc == 0

    def test_internal_exception_is_failopen(self, tmp_path):
        """Garbage JSON on stdin must exit 0, never crash."""
        rc, _, _ = _run(
            CHECK_PY,
            stdin="NOT JSON AT ALL",
            extra_env={"FILE_SCOPE_DIR": str(tmp_path)},
        )
        assert rc == 0

    def test_deeply_nested_path_allowed(self, tmp_path):
        _set(["--session", "e3", "--allow", "src/**"], str(tmp_path))
        rc, _, _ = _check(
            _payload("Edit", "C:/project/src/a/b/c/d/e/f.py", session_id="e3"),
            str(tmp_path),
        )
        assert rc == 0

    def test_notebookedit_in_scope(self, tmp_path):
        _set(["--session", "e4", "--allow", "notebooks/**"], str(tmp_path))
        rc, _, _ = _check(
            _nb_payload("C:/project/notebooks/analysis.ipynb", session_id="e4"),
            str(tmp_path),
        )
        assert rc == 0
