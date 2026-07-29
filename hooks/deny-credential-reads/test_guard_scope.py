#!/usr/bin/env python
"""Regression suite: HARNESS_CREDENTIAL_GUARD must not be documented as switching OFF
credential-file reads that the platform denies unconditionally.

Defect pinned (C46 / D-a089). Two authorities describe credential-file reads:

  * ``agent-self/config/settings.json`` -> ``permissions.deny`` carries FOUR native,
    always-on Read rules (``Read(./.env)``, ``Read(**/.env)``, ``Read(**/*.pem)``,
    ``Read(**/*.credentials*)``). Nothing gates them; the settings ``env`` object does
    not even define ``HARNESS_CREDENTIAL_GUARD``.
  * ``deny.py``'s ``_guard_enabled()`` docstring said the credential-file-READ block is
    "OPT-IN and OFF by default".

Read alone, the second sentence tells a maintainer that clearing the toggle restores
``Read(".env")`` -- it does not. The narrow, correctly-scoped defect is documentation
scope, not a behavioural conflict: ``deny.py``'s MODULE docstring already noted that the
declarative deny covers the Read tool, so the two were never functionally contradictory.

The gate is BIDIRECTIONAL, in the spirit of ``ci/check_skill_dual_write.py``: while those
native rules exist the hook must disclose them, and if someone deletes the rules this
suite fails so the disclosure gets revisited rather than silently rotting.

KNOWN-BROKEN CONTROL IS MANDATORY -- ``PRE_FIX_GUARD_DOCSTRING`` is the byte-exact
pre-fix text and the predicate is asserted to trip on it. A silent detector measures
nothing.
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

THIS = Path(__file__).resolve().parent
DENY = THIS / "deny.py"
REPO = THIS.parent.parent
SETTINGS = REPO / "agent-self" / "config" / "settings.json"

# The four native Read denies whose existence obliges the disclosure.
NATIVE_READ_DENIES = (
    "Read(./.env)",
    "Read(**/.env)",
    "Read(**/*.pem)",
    "Read(**/*.credentials*)",
)

# _guard_enabled's docstring exactly as it stood at 27fb388, before the C46 fix.
PRE_FIX_GUARD_DOCSTRING = """Owner directive 2026-07-11: this credential-file-READ block is OPT-IN and
    OFF by default. It created setbacks in interactive sessions (inspecting one's
    OWN ~/.ssh keys / .env / config, and workflows that merely NAME a credential
    file). Set HARNESS_CREDENTIAL_GUARD=1 (or true/yes/on) to re-enable. Mirrors the
    gate in ~/.agents/harness/modules.py SecretGuardModule so both credential
    mechanisms share ONE toggle. The secret-LITERAL input block and the
    irreversible-op (disk-wipe / history-rewrite) gate are separate and unaffected."""


def _discloses_native_denies(doc: str) -> bool:
    """True when ``doc`` says the native settings deny survives the toggle."""
    low = doc.lower()
    names_the_mechanism = "permissions.deny" in low
    says_not_gated = any(
        phrase in low
        for phrase in ("always-on", "always on", "not gated", "unaffected by")
    )
    scopes_the_claim = "this hook" in low
    return names_the_mechanism and says_not_gated and scopes_the_claim


def _guard_docstring() -> str:
    tree = ast.parse(DENY.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_guard_enabled":
            doc = ast.get_docstring(node)
            assert doc, "_guard_enabled lost its docstring"
            return doc
    raise AssertionError("_guard_enabled not found in deny.py")


def _settings_denies() -> list[str]:
    data = json.loads(SETTINGS.read_text(encoding="utf-8"))
    return list(data.get("permissions", {}).get("deny", []))


# ----------------------------------------------------------------------------------
# known-positive / polarity controls
# ----------------------------------------------------------------------------------
def test_control_detector_fires_on_pre_fix_docstring() -> None:
    assert not _discloses_native_denies(PRE_FIX_GUARD_DOCSTRING), (
        "detector is vacuous: it accepted the pre-fix docstring, so a passing live "
        "assertion would prove nothing"
    )


def test_control_detector_accepts_a_disclosing_docstring() -> None:
    assert _discloses_native_denies(
        "THIS HOOK's block is opt-in. The permissions.deny Read rules are always-on."
    )


# ----------------------------------------------------------------------------------
# the two directions of the gate
# ----------------------------------------------------------------------------------
def test_native_read_denies_are_still_unconditional() -> None:
    """Direction 1: the rules the disclosure talks about must still exist."""
    denies = _settings_denies()
    missing = [r for r in NATIVE_READ_DENIES if r not in denies]
    assert not missing, (
        f"settings.json no longer denies {missing}. That is a POLICY change, not a "
        "test failure to silence: update _guard_enabled's SCOPE note to match."
    )
    env = json.loads(SETTINGS.read_text(encoding="utf-8")).get("env", {})
    assert "HARNESS_CREDENTIAL_GUARD" not in env, (
        "settings.json now sets HARNESS_CREDENTIAL_GUARD; the 'OFF by default' "
        "wording in deny.py needs revisiting"
    )


def test_guard_docstring_discloses_the_always_on_native_denies() -> None:
    """Direction 2: given those rules, the hook must not claim a blanket OFF."""
    doc = _guard_docstring()
    assert _discloses_native_denies(doc), (
        "_guard_enabled's docstring presents the credential-file READ block as wholly "
        "opt-in, but settings.json denies Read on .env/*.pem/*credentials* "
        "unconditionally. Scope the claim to THIS HOOK and name permissions.deny."
    )


# ----------------------------------------------------------------------------------
# behavioural anchor -- the hook really is inert when the toggle is unset
# ----------------------------------------------------------------------------------
def _run_hook(env_value: str | None) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env.pop("HARNESS_CREDENTIAL_GUARD", None)
    if env_value is not None:
        env["HARNESS_CREDENTIAL_GUARD"] = env_value
    return subprocess.run(
        [sys.executable, str(DENY)],
        input=json.dumps({"tool_name": "Read", "tool_input": {"file_path": ".env"}}),
        capture_output=True,
        text=True,
        env=env,
    )


def test_hook_is_silent_when_toggle_unset_and_denies_when_set() -> None:
    """No real credential file is touched -- the payload is a synthetic path."""
    off = _run_hook(None)
    assert off.returncode == 0 and off.stdout.strip() == "", (
        "hook emitted a decision with the toggle unset; the docstring says it is off"
    )
    on = _run_hook("1")
    assert on.returncode == 0, on.stderr
    payload = json.loads(on.stdout)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny", (
        "known-positive control failed: the hook did not recognise the same synthetic "
        "input with the toggle on, so the 'off' row above is not interpretable"
    )
