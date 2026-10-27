#!/usr/bin/env python3
"""Denylist + tool-path coverage for deny-credential-reads/deny.py.

WHY THIS FILE EXISTS (mutation-proven gap, 2026-07-31).
`test_deny.py` is a REGRESSION anchor for one specific bug (the `.env.*` glob
swallowing the public `.env.example` templates). It parametrises only
`.env*`, `id_rsa`, `server.pem` and `credentials`, so it leaves most of
SENSITIVE_GLOBS and most of SECRET_FRAGMENTS unexercised. Measured at main
fcfa30f: deleting every pattern PR #260 added (`id_ecdsa`, `id_dsa`, the two
`*_sk` FIDO variants and `auth.json`) left the whole directory GREEN --

    mutant: python -m pytest hooks/deny-credential-reads -q  ->  32 passed
    mutant: Read C:/Users/x/.ssh/id_ecdsa                    ->  ALLOWED (empty stdout)
    mutant: Read C:/Users/x/.codex/auth.json                 ->  ALLOWED (empty stdout)
    original: Read C:/Users/x/.ssh/id_ecdsa                  ->  permissionDecision=deny

A surviving mutant means the suite was not protecting the fix. This file kills it,
and the two `test_every_*_is_exercised` completeness tests make the NEXT added
pattern fail until somebody writes a case for it.

THE CONTRACT, and the trap it sets for a test author:
`deny()` PRINTS a JSON object with `hookSpecificOutput.permissionDecision == "deny"`
and then exits **0**. Allow is exit 0 with EMPTY stdout. So the two outcomes are
indistinguishable by exit code, and an exit-code assertion passes on a hook that
denies nothing. Every assertion here reads the parsed decision from stdout;
`test_exit_code_alone_cannot_distinguish_deny_from_allow` pins that fact so a future
author cannot "simplify" these into `assert rc == 0`.

The guard is OPT-IN (`HARNESS_CREDENTIAL_GUARD`, owner directive 2026-07-11), so
`_run` sets it explicitly and clears any inherited value.

Run:
    pytest hooks/deny-credential-reads/test_denylist_coverage.py -q
"""

from __future__ import annotations

import fnmatch
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parent / "deny.py"


def _load_deny_module():
    """Import deny.py by path -- the directory name has dashes, so it is not a package."""
    spec = importlib.util.spec_from_file_location("_deny_under_test", HOOK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


deny_mod = _load_deny_module()


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
    """The permissionDecision, or None when the hook stayed silent (= allow)."""
    if not stdout:
        return None
    return json.loads(stdout)["hookSpecificOutput"]["permissionDecision"]


# ---------------------------------------------------------------------------
# The pattern corpus. Each entry is (path, the SENSITIVE_GLOBS it is here for).
# The completeness test below asserts the union covers every declared glob, so
# adding a glob to deny.py without adding a case here turns the suite red.
# ---------------------------------------------------------------------------

SENSITIVE_PATHS = [
    "C:/repo/.env",
    "C:/repo/.env.local",
    "C:/repo/prod.env",
    "C:/repo/deploy.key",
    "C:/repo/server.pem",
    "C:/repo/cert.p12",
    "C:/repo/cert.pfx",
    "C:/repo/cert.pkcs12",
    "C:/repo/credentials",
    "C:/repo/credentials.json",
    "C:/Users/x/.aws/aws_credentials_backup",
    "C:/Users/x/.credentials.json",
    # all four ssh-keygen -t defaults, plus the two FIDO *_sk variants and .pub siblings.
    # id_ecdsa / id_dsa / *_sk were the PR #260 additions no test covered.
    "C:/Users/x/.ssh/id_rsa",
    "C:/Users/x/.ssh/id_rsa.pub",
    "C:/Users/x/.ssh/id_ed25519",
    "C:/Users/x/.ssh/id_ed25519.pub",
    "C:/Users/x/.ssh/id_ecdsa",
    "C:/Users/x/.ssh/id_ecdsa.pub",
    "C:/Users/x/.ssh/id_ecdsa_sk",
    "C:/Users/x/.ssh/id_ecdsa_sk.pub",
    "C:/Users/x/.ssh/id_ed25519_sk",
    "C:/Users/x/.ssh/id_ed25519_sk.pub",
    "C:/Users/x/.ssh/id_dsa",
    "C:/Users/x/.ssh/id_dsa.pub",
    # the Codex/ChatGPT credential store holding a live refresh_token
    "C:/Users/x/.codex/auth.json",
    "C:/repo/secrets.yaml",
    "C:/repo/api.secret",
    "C:/Users/x/.netrc",
    "C:/Users/x/.pgpass",
]

# Ordinary paths that MUST stay readable. Deliberately includes near-misses of the
# credential names so an over-broad glob is caught as well as an under-broad one.
ORDINARY_PATHS = [
    "C:/repo/package.json",
    "C:/repo/README.md",
    "C:/repo/src/main.py",
    "C:/repo/.env.example",
    "C:/repo/.env.template",
    "C:/repo/.env.sample",
    "C:/repo/id_rsa_rotation_notes.md",
    "C:/repo/monkey.py",
    "C:/repo/settings.json",
    "C:/repo/keyboard.ts",
]


@pytest.mark.parametrize("path", SENSITIVE_PATHS)
def test_credential_read_is_denied(path):
    rc, out = _run({"tool_name": "Read", "tool_input": {"file_path": path}})
    assert rc == 0
    assert _decision(out) == "deny", f"{path} must be denied, got {out!r}"


@pytest.mark.parametrize("path", ORDINARY_PATHS)
def test_ordinary_read_is_allowed(path):
    rc, out = _run({"tool_name": "Read", "tool_input": {"file_path": path}})
    assert rc == 0
    assert _decision(out) is None, f"{path} must be allowed, got {out!r}"


def test_every_sensitive_glob_is_exercised():
    """Completeness gate: no glob in deny.py may go untested.

    This is the test that would have caught PR #260's gap at authoring time --
    it fails the moment a pattern is added to SENSITIVE_GLOBS with no case above.
    """
    covered = set()
    for path in SENSITIVE_PATHS:
        base = os.path.basename(path).lower()
        low = path.replace("\\", "/").lower()
        for glob in deny_mod.SENSITIVE_GLOBS:
            gl = glob.lower()
            if fnmatch.fnmatch(base, gl) or fnmatch.fnmatch(low, "*/" + gl):
                covered.add(glob)
    missing = sorted(set(deny_mod.SENSITIVE_GLOBS) - covered)
    assert not missing, (
        "SENSITIVE_GLOBS entries with no case in SENSITIVE_PATHS: "
        + ", ".join(missing)
        + " -- add a path that exercises each, or the denylist entry is unprotected."
    )


# ---------------------------------------------------------------------------
# Bash / PowerShell: the read-verb-near-a-secret-fragment path
# ---------------------------------------------------------------------------

SECRET_COMMANDS = [
    "cat .env",
    "cat .env.local",
    "grep KEY credentials",
    "rg TOKEN ~/.aws/credentials",
    "cat ~/.ssh/id_rsa",
    "cat ~/.ssh/id_ed25519",
    "cat ~/.ssh/id_ecdsa",
    "cat ~/.ssh/id_ecdsa_sk",
    "cat ~/.ssh/id_dsa",
    "cat ~/.codex/auth.json",
    "head -5 server.pem",
    "base64 deploy.key",
    "cat ~/.netrc",
    "tail ~/.pgpass",
    "xxd cert.p12",
    "strings cert.pfx",
    "Get-Content ~/.ssh/id_ecdsa",
    "select-string TOKEN .env",
]

ORDINARY_COMMANDS = [
    "echo hello",
    "ls -la",
    "git status",
    "cat README.md",
    "cat .env.example",
    "python -m pytest -q",
]


@pytest.mark.parametrize("command", SECRET_COMMANDS)
def test_secret_bash_command_is_denied(command):
    rc, out = _run({"tool_name": "Bash", "tool_input": {"command": command}})
    assert rc == 0
    assert _decision(out) == "deny", f"{command!r} must be denied, got {out!r}"


@pytest.mark.parametrize("command", ORDINARY_COMMANDS)
def test_ordinary_bash_command_is_allowed(command):
    rc, out = _run({"tool_name": "Bash", "tool_input": {"command": command}})
    assert rc == 0
    assert _decision(out) is None, f"{command!r} must be allowed, got {out!r}"


def test_every_secret_fragment_is_exercised():
    """Completeness gate for the near-a-read-verb fragment list."""
    covered = set()
    for command in SECRET_COMMANDS:
        low = command.lower()
        for fragment in deny_mod.SECRET_FRAGMENTS:
            pattern = (
                deny_mod.READ_VERBS
                + r"[^\n|;&<>]*(?:"
                + deny_mod._fragment_pattern(fragment)
                + r")"
            )
            if re.search(pattern, low):
                covered.add(fragment)
    missing = sorted(set(deny_mod.SECRET_FRAGMENTS) - covered)
    assert not missing, (
        "SECRET_FRAGMENTS entries with no case in SECRET_COMMANDS: "
        + ", ".join(missing)
        + " -- add a command that exercises each."
    )


# ---------------------------------------------------------------------------
# Tool-path matrix: main() dispatches on tool_name and reads a DIFFERENT input
# key per branch, so a branch with the wrong key silently never denies.
# ---------------------------------------------------------------------------

CRED = "C:/Users/x/.ssh/id_ecdsa"
PLAIN = "C:/repo/README.md"

TOOL_PAYLOADS = [
    ("Read", {"file_path": CRED}, {"file_path": PLAIN}),
    ("Edit", {"file_path": CRED}, {"file_path": PLAIN}),
    ("MultiEdit", {"file_path": CRED}, {"file_path": PLAIN}),
    ("NotebookEdit", {"notebook_path": CRED}, {"notebook_path": PLAIN}),
    ("Grep", {"path": CRED}, {"path": PLAIN}),
    ("Bash", {"command": "cat " + CRED}, {"command": "cat " + PLAIN}),
    (
        "PowerShell",
        {"command": "Get-Content " + CRED},
        {"command": "Get-Content " + PLAIN},
    ),
]


@pytest.mark.parametrize("tool,sensitive_input", [(t, s) for t, s, _ in TOOL_PAYLOADS])
def test_tool_path_denies_credential(tool, sensitive_input):
    rc, out = _run({"tool_name": tool, "tool_input": sensitive_input})
    assert rc == 0
    assert _decision(out) == "deny", f"{tool} must deny {sensitive_input}, got {out!r}"


@pytest.mark.parametrize("tool,plain_input", [(t, p) for t, _, p in TOOL_PAYLOADS])
def test_tool_path_allows_ordinary(tool, plain_input):
    rc, out = _run({"tool_name": tool, "tool_input": plain_input})
    assert rc == 0
    assert _decision(out) is None, f"{tool} must allow {plain_input}, got {out!r}"


def test_unhandled_tool_is_not_denied():
    """A tool outside the dispatch (WebFetch) falls through to the normal flow."""
    rc, out = _run(
        {"tool_name": "WebFetch", "tool_input": {"url": "https://x/id_ecdsa"}}
    )
    assert rc == 0
    assert _decision(out) is None


# ---------------------------------------------------------------------------
# Contract + robustness pins
# ---------------------------------------------------------------------------


def test_exit_code_alone_cannot_distinguish_deny_from_allow():
    """Pins the trap in the module docstring: BOTH outcomes exit 0.

    If this ever fails because deny() started exiting non-zero, the assertions in
    this file are stricter than necessary but still correct -- update deliberately.
    """
    deny_rc, deny_out = _run({"tool_name": "Read", "tool_input": {"file_path": CRED}})
    allow_rc, allow_out = _run(
        {"tool_name": "Read", "tool_input": {"file_path": PLAIN}}
    )
    assert deny_rc == allow_rc == 0
    assert _decision(deny_out) == "deny"
    assert _decision(allow_out) is None
    assert deny_out != allow_out, "stdout is the ONLY channel that carries the decision"


@pytest.mark.parametrize(
    "path", ["C:/Users/x/.ssh/ID_ECDSA", "C:/Users/x/.CODEX/Auth.Json"]
)
def test_denylist_is_case_insensitive(path):
    rc, out = _run({"tool_name": "Read", "tool_input": {"file_path": path}})
    assert rc == 0
    assert _decision(out) == "deny", (
        f"{path} must be denied case-insensitively: {out!r}"
    )


@pytest.mark.parametrize(
    "path", ['"C:/Users/x/.ssh/id_dsa"', "'C:/Users/x/.ssh/id_dsa'"]
)
def test_quoted_path_is_still_denied(path):
    rc, out = _run({"tool_name": "Read", "tool_input": {"file_path": path}})
    assert rc == 0
    assert _decision(out) == "deny", f"{path} must be denied when quoted: {out!r}"


def test_backslash_path_is_denied():
    rc, out = _run(
        {"tool_name": "Read", "tool_input": {"file_path": r"C:\Users\x\.ssh\id_ecdsa"}}
    )
    assert rc == 0
    assert _decision(out) == "deny"


@pytest.mark.parametrize("path", SENSITIVE_PATHS[:5])
def test_guard_off_by_default_allows_everything_this_hook_gates(path):
    """Owner directive 2026-07-11: THIS hook is opt-in.

    The always-on native permissions.deny rules in settings.json are a separate,
    ungated mechanism -- see test_guard_scope.py, which pins that boundary.
    """
    rc, out = _run({"tool_name": "Read", "tool_input": {"file_path": path}}, guard=None)
    assert rc == 0
    assert _decision(out) is None


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on", " on "])
def test_guard_toggle_accepts_every_documented_truthy_value(value):
    rc, out = _run(
        {"tool_name": "Read", "tool_input": {"file_path": CRED}}, guard=value
    )
    assert rc == 0
    assert _decision(out) == "deny", f"HARNESS_CREDENTIAL_GUARD={value!r} must enable"


@pytest.mark.parametrize("value", ["0", "false", "no", "off", ""])
def test_guard_toggle_rejects_falsy_values(value):
    rc, out = _run(
        {"tool_name": "Read", "tool_input": {"file_path": CRED}}, guard=value
    )
    assert rc == 0
    assert _decision(out) is None


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"tool_name": "Read"},
        {"tool_name": "Read", "tool_input": None},
        {"tool_name": "Read", "tool_input": {}},
        {"tool_name": None, "tool_input": {"file_path": CRED}},
    ],
)
def test_degenerate_payloads_fail_open(payload):
    """AGENTS.md section 6: any internal error exits 0 so the harness never wedges."""
    rc, out = _run(payload)
    assert rc == 0
    assert _decision(out) is None


def test_deny_reason_names_the_indirection_remedy():
    """The denial must tell the agent what to do instead, not just say no."""
    _, out = _run({"tool_name": "Read", "tool_input": {"file_path": CRED}})
    reason = json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"]
    assert "no-raw-credentials" in reason
    assert "${" in reason, "the reason must show the env-indirection remedy"


def test_deny_payload_shape_matches_the_pretooluse_contract():
    _, out = _run({"tool_name": "Read", "tool_input": {"file_path": CRED}})
    hook_output = json.loads(out)["hookSpecificOutput"]
    assert hook_output["hookEventName"] == "PreToolUse"
    assert set(hook_output) == {
        "hookEventName",
        "permissionDecision",
        "permissionDecisionReason",
    }
