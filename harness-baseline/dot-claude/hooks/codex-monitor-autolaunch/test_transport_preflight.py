#!/usr/bin/env python3
"""Regression suite for the cross-vendor transport-contract preflight (D-a004).

WHY THIS EXISTS
---------------
``rules/common/cross-vendor-dispatch.md`` bans fire-and-forget work-unit dispatch
(:7-17) and requires an exit/output-file/schema AND-gate, prompt-by-file transport,
``--ignore-user-config``, a terminal SUCCESS/FAILED result and an explicit 30-minute
timeout (:19-30, :32-46, :55-66). ``agents/codex.md`` embodies all of it.

Measured gap (D-a004, adjudicated STILL_TRUE): for a raw ``codex exec`` typed into a
Bash/PowerShell command, ``hooks/_dispatch/manifest.json`` selected exactly ONE check --
``codex-monitor-autolaunch`` -- and that check only opened a read-only dashboard. Nothing
on the tool path mentioned the transport contract, so a noncanonical invocation entered
the tool path with none of the adapter's guarantees.

Two properties are load-bearing here and each has a test below:

1. The dispatcher is INJECT-ONLY (``hooks/_dispatch/dispatch.py:44-45``). The preflight
   must therefore ADVISE, never ``exit 2`` -- an exit-2 gate folded into the dispatcher is
   silently disarmed (``hooks/_dispatch/test_manifest_presence.py:51-53``).
2. ``CODEX_MONITOR_AUTOLAUNCH=off`` suppresses MONITORING only. It must not suppress the
   contract advisory, or the opt-out would silently re-open the whole gap.

Run:
    pytest hooks/codex-monitor-autolaunch/test_transport_preflight.py -v
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

THIS = Path(__file__).resolve().parent


def _load():
    """Import check.py under a synthetic name (the hook dir name is not importable)."""
    spec = importlib.util.spec_from_file_location(
        "codex_monitor_autolaunch_check", THIS / "check.py"
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


check = _load()

# The canonical invocation from agents/codex.md:28-36 -- prompt on stdin from a file,
# clean config, an -o result channel, foreground.
CANONICAL = (
    'codex exec --cd "C:/wd" --skip-git-repo-check --ignore-user-config '
    "--dangerously-bypass-approvals-and-sandbox "
    '--output-schema "C:/wd/.codex-adapter/schema.json" '
    '-o "C:/wd/.codex-adapter/last-message.json" '
    '--model gpt-5.6-sol - < "C:/wd/.codex-adapter/prompt.txt"'
)

# The exact noncanonical command named in the D-a004 evidence.
NONCANONICAL = 'codex exec --model gpt-5.6-sol "inline prompt"'


def _payload(command: str, *, tool: str = "Bash", **tool_input):
    ti = {"command": command}
    ti.update(tool_input)
    return {"tool_name": tool, "tool_input": ti, "session_id": "sess-test"}


# --------------------------------------------------------------------------- detector


def test_noncanonical_codex_exec_is_flagged():
    """The evidence command must raise transport-contract violations."""
    violations = check.transport_violations(_payload(NONCANONICAL, timeout=1800000))
    assert violations, "a raw inline `codex exec` must violate the transport contract"


@pytest.mark.parametrize(
    "token",
    ("ignore-user-config", "prompt", "result"),
)
def test_noncanonical_names_each_missing_guarantee(token: str):
    """Each violation names the guarantee it is about, so the advice is actionable."""
    blob = " ".join(
        check.transport_violations(_payload(NONCANONICAL, timeout=1800000))
    ).lower()
    assert token in blob, f"expected a violation mentioning {token!r}; got: {blob!r}"


def test_canonical_invocation_is_clean():
    """The adapter's own command must produce ZERO violations (no false positive)."""
    violations = check.transport_violations(_payload(CANONICAL, timeout=1800000))
    assert violations == [], f"canonical invocation flagged: {violations}"


@pytest.mark.parametrize(
    "command",
    (
        CANONICAL + " &",
        "nohup " + CANONICAL,
        CANONICAL + " --background",
    ),
)
def test_background_forms_are_flagged(command: str):
    """rules/common/cross-vendor-dispatch.md:7-17 -- fire-and-forget dispatch is banned."""
    blob = " ".join(check.transport_violations(_payload(command, timeout=1800000)))
    assert "background" in blob.lower(), f"background form not flagged: {command!r}"


def test_run_in_background_tool_param_is_flagged():
    """The Bash tool's own run_in_background param backgrounds it just as hard."""
    blob = " ".join(
        check.transport_violations(
            _payload(CANONICAL, timeout=1800000, run_in_background=True)
        )
    )
    assert "background" in blob.lower()


def test_missing_explicit_timeout_is_flagged():
    """agents/codex.md:50 -- the silent 10-min default must never be taken."""
    blob = " ".join(check.transport_violations(_payload(CANONICAL))).lower()
    assert "timeout" in blob


def test_short_timeout_is_flagged():
    blob = " ".join(check.transport_violations(_payload(CANONICAL, timeout=600000)))
    assert "timeout" in blob.lower()


@pytest.mark.parametrize(
    "payload",
    (
        _payload("git status"),
        _payload("echo codex is great"),
        {"tool_name": "Read", "tool_input": {"file_path": "codex exec"}},
        {},
    ),
)
def test_non_dispatch_payloads_are_silent(payload):
    """No false positives on ordinary tool use -- only a real `codex exec` counts."""
    assert check.transport_violations(payload) == []


def test_codex_mcp_is_not_a_work_unit_dispatch():
    """`codex mcp` starts the MCP server; it is not a work-unit dispatch."""
    assert check.transport_violations(_payload("codex mcp-server")) == []


def test_documented_repair_step_is_not_nagged():
    """agents/codex.md:76 -- ONE `codex exec resume --last` is the adapter's own repair
    ladder, not a fresh dispatch. Flagging it would nag the canonical path."""
    assert check.transport_violations(_payload("codex exec resume --last")) == []


# ------------------------------------------------------------------- wiring via main()


def _run_main(payload: dict, monkeypatch, *, monitor: str = "off") -> str:
    """Drive main() with the dashboard launch disabled; return captured stdout."""
    monkeypatch.setenv("CODEX_MONITOR_AUTOLAUNCH", monitor)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    buf = io.StringIO()
    monkeypatch.setattr(sys, "stdout", buf)
    # Belt and braces: a launch must never happen from a test.
    monkeypatch.setattr(check, "_launch", lambda: False)
    check.main()
    return buf.getvalue()


def _contexts(out: str) -> list[str]:
    ctx = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        ctx.append(obj["hookSpecificOutput"]["additionalContext"])
    return ctx


def test_advisory_survives_the_monitor_optout(monkeypatch):
    """THE core regression: CODEX_MONITOR_AUTOLAUNCH=off suppresses MONITORING only.

    D-a004 measured `CODEX_MONITOR_AUTOLAUNCH=off` -> aggregate=None, dispatcher_stdout=''.
    With the preflight in place the contract advisory must still reach the model.
    """
    out = _run_main(_payload(NONCANONICAL, timeout=1800000), monkeypatch, monitor="off")
    blob = " ".join(_contexts(out))
    assert "agents/codex.md" in blob, (
        "the opt-out suppressed the transport-contract advisory -- D-a004 is re-opened"
    )


def test_advisory_emits_pretooluse_event_shape(monkeypatch):
    out = _run_main(_payload(NONCANONICAL, timeout=1800000), monkeypatch)
    objs = [json.loads(x) for x in out.splitlines() if x.strip()]
    assert objs, "expected at least one hook JSON line"
    for obj in objs:
        assert obj["hookSpecificOutput"]["hookEventName"] == "PreToolUse"


def test_main_is_inject_only_and_never_blocks(monkeypatch):
    """dispatch.py is inject-only: main() must return None and never raise/exit."""
    assert (
        check.main.__module__ == "codex_monitor_autolaunch_check"
    )  # sanity: we patched the right module
    out = _run_main(_payload(NONCANONICAL, timeout=1800000), monkeypatch)
    # A blocking gate would exit(2); reaching here at all proves it returned normally.
    assert isinstance(out, str)


def test_canonical_dispatch_emits_no_advisory(monkeypatch):
    """A compliant command must not nag."""
    out = _run_main(_payload(CANONICAL, timeout=1800000), monkeypatch, monitor="off")
    assert "transport contract" not in out.lower()


def test_malformed_payload_fails_open(monkeypatch):
    """Fail-open (check.py:15-17): garbage in must not raise."""
    monkeypatch.setenv("CODEX_MONITOR_AUTOLAUNCH", "off")
    monkeypatch.setattr(sys, "stdin", io.StringIO("{not json"))
    buf = io.StringIO()
    monkeypatch.setattr(sys, "stdout", buf)
    check.main()
    assert buf.getvalue() == ""
