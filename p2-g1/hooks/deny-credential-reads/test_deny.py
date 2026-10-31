#!/usr/bin/env python3
"""Tests for deny-credential-reads/deny.py.

Regression anchor (D-a080): with HARNESS_CREDENTIAL_GUARD=1 the `.env.*` glob
classified the PUBLIC placeholder templates `.env.example` / `.env.template` /
`.env.sample` as credential files and denied them, which deterministically
blocked the first required step of `commands/update-docs.md:29`
("Read `.env.example` (or `.env.template`, `.env.sample`)").

Every test drives the hook the way Claude Code does: JSON payload on stdin,
environment, exit code, stdout.  The guard is opt-in, so the enabled tests set
HARNESS_CREDENTIAL_GUARD explicitly and the disabled control clears it.

Run:
    pytest hooks/deny-credential-reads/test_deny.py -q
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parent / "deny.py"

PUBLIC_TEMPLATES = (".env.example", ".env.template", ".env.sample")


def _run(payload: dict, guard: str | None = "1") -> tuple[int, str]:
    env = os.environ.copy()
    env.pop("HARNESS_CREDENTIAL_GUARD", None)
    if guard is not None:
        env["HARNESS_CREDENTIAL_GUARD"] = guard
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    return proc.returncode, proc.stdout.strip()


def _decision(stdout: str) -> str | None:
    """Return the permissionDecision, or None when the hook stayed silent."""
    if not stdout:
        return None
    return json.loads(stdout)["hookSpecificOutput"]["permissionDecision"]


def _read(path: str) -> dict:
    return {"tool_name": "Read", "tool_input": {"file_path": path}}


def _bash(command: str) -> dict:
    return {"tool_name": "Bash", "tool_input": {"command": command}}


# ---------------------------------------------------------------------------
# The regression: public templates must be readable when the guard is ENABLED
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", PUBLIC_TEMPLATES)
def test_public_template_read_is_allowed_when_guard_enabled(name):
    rc, out = _run(_read(f"C:/repo/{name}"))
    assert rc == 0
    assert _decision(out) is None, f"{name} must not be denied: {out}"


@pytest.mark.parametrize("name", PUBLIC_TEMPLATES)
def test_public_template_grep_is_allowed_when_guard_enabled(name):
    rc, out = _run({"tool_name": "Grep", "tool_input": {"path": f"C:/repo/{name}"}})
    assert rc == 0
    assert _decision(out) is None, f"{name} must not be denied: {out}"


@pytest.mark.parametrize("name", PUBLIC_TEMPLATES)
def test_public_template_bash_read_is_allowed_when_guard_enabled(name):
    rc, out = _run(_bash(f"cat {name}"))
    assert rc == 0
    assert _decision(out) is None, f"cat {name} must not be denied: {out}"


# ---------------------------------------------------------------------------
# The exemption must stay exact: real credential files still denied
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "C:/repo/.env",
        "C:/repo/.env.local",
        "C:/repo/.env.production",
        # near-misses of the template names -- conservative, still sensitive
        "C:/repo/.env.examples",
        "C:/repo/.env.example.bak",
        "C:/repo/id_rsa",
        "C:/repo/server.pem",
        "C:/repo/credentials",
    ],
)
def test_real_credential_read_is_still_denied(path):
    rc, out = _run(_read(path))
    assert rc == 0
    assert _decision(out) == "deny", f"{path} must stay denied: {out!r}"


@pytest.mark.parametrize(
    "command",
    [
        "cat .env",
        "cat .env.local",
        "cat .env.examples",
        "cat .env.example.bak",
        "cat .env.example .env",
        "grep KEY credentials",
        "get-content id_rsa",
    ],
)
def test_real_credential_bash_read_is_still_denied(command):
    rc, out = _run(_bash(command))
    assert rc == 0
    assert _decision(out) == "deny", f"{command!r} must stay denied: {out!r}"


# ---------------------------------------------------------------------------
# Controls: the failure is specific to name classification, not a dead script
# ---------------------------------------------------------------------------


def test_non_sensitive_read_is_allowed():
    rc, out = _run(_read("C:/repo/package.json"))
    assert rc == 0
    assert _decision(out) is None


def test_guard_is_off_by_default():
    """Owner directive 2026-07-11: the credential-file block is opt-in."""
    rc, out = _run(_read("C:/repo/.env"), guard=None)
    assert rc == 0
    assert _decision(out) is None


def test_malformed_stdin_fails_open():
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input="not json",
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""
