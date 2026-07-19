#!/usr/bin/env python3
"""Regression tests for the live local-hook dispatcher registrations.

These tests intentionally inspect both registration documents.  ``settings.json``
is the active user-level wire, while ``hooks/hooks.json`` is also checked so a
future plugin/manual registration cannot silently reintroduce one of the Python
hooks already consolidated behind ``_dispatch``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest


HERE = Path(__file__).resolve().parent
HOOKS_ROOT = HERE.parent
CLAUDE_ROOT = HOOKS_ROOT.parent
MANIFEST = HERE / "manifest.json"
SETTINGS = CLAUDE_ROOT / "settings.json"
HOOKS_JSON = HOOKS_ROOT / "hooks.json"
DISPATCH = HERE / "dispatch.py"
NO_FORCE_PUSH = HOOKS_ROOT / "no-force-push" / "hook.py"

DISPATCH_EVENTS = {
    "SessionStart": "sessionstart",
    "PreToolUse": "pretooluse",
    "PostToolUse": "posttooluse",
    "Stop": "stop",
}

# Tier-1.1 compatibility census.  These handlers only emit additionalContext
# (or perform silent side effects), which is the full contract implemented by
# dispatch.py today.  Keep this explicit: deriving an expectation from the
# manifest itself would let a dropped handler make its own regression test pass.
EXPECTED_DISPATCH_CHECKS = {
    "PreToolUse": {
        "goal-reinject/reinject": "goal-reinject/reinject.py",
        "compchem-preflight": "compchem-preflight/probe.py",
        "strong-tool-nudge": "strong-tool-nudge/check.py",
        "mcp-liveness/pretool": "mcp-liveness/liveness.py",
        "edit-checkpoints": "edit-checkpoints/checkpoint.py",
        "bg-registry/register": "bg-registry/register.py",
        "memory-spool/spool": "memory-spool/spool.py",
        "dup-guard": "dup-guard/guard.py",
        "contraindication": "contraindication/check.py",
        "iatrogenics": "iatrogenics/gate.py",
    },
    "PostToolUse": {
        "anti-degen/fingerprint": "anti-degen/fingerprint.py",
        "claim-guard/ledger-write": "claim-guard/ledger-write.py",
        "memory-guard/scan": "memory-guard/scan.py",
        "edit-validate/record": "edit-validate/record.py",
        "fresh-verify/trigger": "fresh-verify/trigger.py",
        "orphan-commit": "orphan-commit/check.py",
        "semantic-router/observe": "semantic-router/observe.py",
        "memory-spool/flush_check": "memory-spool/flush_check.py",
        "tool-result-sentinel": "tool-result-sentinel/sentinel.py",
        "stub-ledger/record": "stub-ledger/record.py",
    },
}

EXPECTED_DISPATCH_ROUTES = {
    "PreToolUse": {
        "goal-reinject/reinject": ([], "Edit|Write|Bash", 12, True),
        "compchem-preflight": (
            [],
            "mcp__schrodinger__glide_dock|mcp__schrodinger__prime_mmgbsa",
            8,
            True,
        ),
        "strong-tool-nudge": ([], "Bash|Write|Edit|MultiEdit", 8, True),
        "mcp-liveness/pretool": (["pretool"], "mcp__basic-memory__.*", 12, True),
        "edit-checkpoints": ([], "Edit|Write|MultiEdit", 15, False),
        "bg-registry/register": ([], "Task", 5, False),
        "memory-spool/spool": (
            [],
            "mcp__basic-memory__write_note|mcp__basic-memory__edit_note",
            5,
            False,
        ),
        "dup-guard": ([], "Write", 8, True),
        "contraindication": (
            [],
            "Bash|PowerShell|Edit|Write|MultiEdit|mcp__frida-mcp__.*|mcp__cheatengine__.*",
            12,
            True,
        ),
        "iatrogenics": (
            [],
            "Edit|Write|Bash|mcp__cheatengine__.*|mcp__frida-mcp__.*",
            12,
            True,
        ),
    },
    "PostToolUse": {
        "anti-degen/fingerprint": (
            [],
            "Bash|mcp__ida-pro-mcp__.*|mcp__ghidra-mcp__.*|mcp__frida-mcp__.*|mcp__binary-ninja-mcp__.*",
            10,
            True,
        ),
        "claim-guard/ledger-write": ([], "Bash", 5, False),
        "memory-guard/scan": ([], ".*", 10, True),
        "edit-validate/record": ([], "Edit|Write|MultiEdit", 5, False),
        "fresh-verify/trigger": (
            [],
            "mcp__ida-pro-mcp__.*|mcp__cheatengine__.*|mcp__ghidra-mcp__.*",
            8,
            True,
        ),
        "orphan-commit": ([], "Bash", 20, True),
        "semantic-router/observe": ([], "Skill|Task|mcp__.*", 8, False),
        "memory-spool/flush_check": (
            ["posttool"],
            "mcp__basic-memory__write_note|mcp__basic-memory__edit_note",
            5,
            True,
        ),
        "tool-result-sentinel": ([], ".*", 8, True),
        "stub-ledger/record": ([], "Edit|Write|MultiEdit", 6, False),
    },
}

# These ten handlers use an enforcement or mutation contract which the current
# inject-only dispatcher cannot preserve.  An exit-2 gate, permission decision,
# updatedInput, or updatedToolOutput must stay a separate Claude hook until the
# dispatcher grows explicit merge/precedence semantics for those fields.
REQUIRED_STANDALONE_HANDLERS = {
    "PreToolUse": {
        "test-tamper-guard/guard.py": ("Bash", 20, ""),
        "cmd-rewrite/inject-nopager.py": ("Bash", 5, ""),
        "ulysses/enforce.py": (
            "Edit|Write|MultiEdit|Bash|PowerShell|mcp__cheatengine__.*|mcp__frida-mcp__.*",
            10,
            "",
        ),
        "re-autolaunch/autolaunch.py": (
            "mcp__ida-pro-mcp__.*|mcp__ghidra-mcp__.*|mcp__binary-ninja-mcp__.*",
            12,
            "pretool",
        ),
        "tms/stale_anchor.py": (
            "mcp__ida-pro-mcp__.*|mcp__ghidra-mcp__.*|mcp__binary-ninja-mcp__.*|mcp__frida-mcp__.*|mcp__cheatengine__.*",
            8,
            "",
        ),
        "file-scope/check.py": ("Edit|Write|MultiEdit|NotebookEdit", 10, ""),
        "loop-recovery/handler.py": ("Bash", 5, "--mode pretooluse"),
        "deny-credential-reads/deny.py": (
            "Read|Edit|MultiEdit|Grep|Bash|PowerShell",
            8,
            "",
        ),
    },
    "PostToolUse": {
        "cmd-rewrite/compress-output.py": ("Bash", 10, ""),
        "per-edit-check/check.py": ("Edit|Write|MultiEdit", 12, ""),
    },
}


def _load(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"{path} must contain a JSON object"
    return data


def _hook_entries(document: dict, event: str | None = None):
    hooks = document.get("hooks") or {}
    assert isinstance(hooks, dict), "top-level hooks must be an object"
    event_items = [(event, hooks.get(event) or [])] if event else hooks.items()
    for event_name, groups in event_items:
        assert isinstance(groups, list), f"hooks.{event_name} must be a list"
        for group in groups:
            assert isinstance(group, dict), (
                f"hooks.{event_name} group must be an object"
            )
            commands = group.get("hooks") or []
            assert isinstance(commands, list), (
                f"hooks.{event_name}[].hooks must be a list"
            )
            for hook in commands:
                if isinstance(hook, dict) and hook.get("type") == "command":
                    yield event_name, group, hook


def _norm(value: str | Path) -> str:
    return str(value).replace("\\", "/").casefold()


def _matcher_equivalent(actual: object, expected: str) -> bool:
    """Treat a flat regex alternation as order-insensitive."""

    if not isinstance(actual, str):
        return False
    return actual == expected or set(actual.split("|")) == set(expected.split("|"))


def _commands_referencing(document: dict, path: Path, event: str | None = None):
    needle = _norm(path)
    return [
        (event_name, group, hook)
        for event_name, group, hook in _hook_entries(document, event)
        if needle in _norm(str(hook.get("command") or ""))
    ]


@pytest.mark.parametrize("event,token", DISPATCH_EVENTS.items())
def test_settings_has_exactly_one_local_dispatch_for_event(event: str, token: str):
    settings = _load(SETTINGS)
    matches = _commands_referencing(settings, DISPATCH, event)
    assert len(matches) == 1, (
        f"hooks.{event} must contain exactly one local _dispatch command; "
        f"found {len(matches)}"
    )
    command = str(matches[0][2].get("command") or "").strip()
    assert re.search(rf"(?:^|\s){re.escape(token)}\s*$", command, re.IGNORECASE), (
        f"hooks.{event} local dispatcher must receive the {token!r} event token: {command!r}"
    )

    manifest_event = _load(MANIFEST)["events"][event]
    expected_matcher = manifest_event.get("settings_matcher")
    actual_matcher = matches[0][1].get("matcher")
    if expected_matcher == "*":
        assert actual_matcher in {"*", ".*"}, (
            f"hooks.{event} must match every event subtype, got {actual_matcher!r}"
        )
    else:
        assert actual_matcher == expected_matcher, (
            f"hooks.{event} matcher {actual_matcher!r} does not mirror manifest "
            f"settings_matcher {expected_matcher!r}"
        )
    assert matches[0][2].get("timeout", 0) >= manifest_event["settings_timeout"], (
        f"hooks.{event} timeout must cover the manifest's dispatcher budget"
    )


def test_no_force_push_is_a_standalone_bash_gate():
    settings = _load(SETTINGS)
    matches = _commands_referencing(settings, NO_FORCE_PUSH, "PreToolUse")
    assert len(matches) == 1, (
        "hooks.PreToolUse must contain exactly one standalone no-force-push command"
    )
    _event, group, hook = matches[0]
    assert group.get("matcher") == "Bash"
    assert len(group.get("hooks") or []) == 1, (
        "no-force-push must remain its own hook group"
    )
    assert hook.get("timeout") == 8

    manifest = _load(MANIFEST)
    manifest_scripts = {
        _norm(check.get("script") or "")
        for event_data in (manifest.get("events") or {}).values()
        for check in (event_data.get("checks") or [])
        if isinstance(event_data, dict) and isinstance(check, dict)
    }
    assert _norm(NO_FORCE_PUSH.relative_to(HOOKS_ROOT)) not in manifest_scripts, (
        "the exit-2 no-force-push gate must not be folded into the exit-0 dispatcher"
    )


@pytest.mark.parametrize("event", ("PreToolUse", "PostToolUse"))
def test_prepost_manifest_entries_are_unique_and_reference_files(event: str):
    manifest = _load(MANIFEST)
    event_data = (manifest.get("events") or {}).get(event) or {}
    checks = event_data.get("checks") or []
    assert checks, f"events.{event}.checks must not be empty"

    names = [check.get("name") for check in checks]
    assert all(isinstance(name, str) and name.strip() for name in names)
    assert len(names) == len(set(names)), f"events.{event} check names must be unique"

    root = Path(manifest.get("hooks_root") or HOOKS_ROOT)
    for check in checks:
        script = check.get("script")
        assert isinstance(script, str) and script.strip(), (
            f"events.{event} check {check.get('name')!r} must name a script"
        )
        assert (root / script).is_file(), (
            f"events.{event} check {check.get('name')!r} points to missing {root / script}"
        )


@pytest.mark.parametrize("event", ("PreToolUse", "PostToolUse"))
def test_prepost_manifest_contains_every_dispatch_compatible_handler(event: str):
    manifest = _load(MANIFEST)
    checks = manifest["events"][event]["checks"]
    actual = {check.get("name"): check.get("script") for check in checks}
    expected = EXPECTED_DISPATCH_CHECKS[event]

    missing = {
        name: script for name, script in expected.items() if actual.get(name) != script
    }
    assert not missing, (
        f"events.{event} is missing dispatcher-compatible Tier-1.1 handlers: {missing}"
    )

    route_failures: list[str] = []
    for name, (args, matcher, timeout, emits) in EXPECTED_DISPATCH_ROUTES[
        event
    ].items():
        check = next((item for item in checks if item.get("name") == name), None)
        if check is None:
            continue
        expected_fields = {
            "args": args,
            "matcher": matcher,
            "timeout": timeout,
            "emits": emits,
        }
        for field, expected_value in expected_fields.items():
            equivalent = (
                _matcher_equivalent(check.get(field), expected_value)
                if field == "matcher"
                else check.get(field) == expected_value
            )
            if not equivalent:
                route_failures.append(
                    f"{name}.{field}={check.get(field)!r}, expected {expected_value!r}"
                )
    assert not route_failures, "dispatcher routing regressions:\n" + "\n".join(
        route_failures
    )


@pytest.mark.parametrize("event", ("PreToolUse", "PostToolUse"))
def test_incompatible_gates_and_transformers_remain_standalone(event: str):
    settings = _load(SETTINGS)
    manifest = _load(MANIFEST)
    manifest_scripts = {
        _norm(check.get("script") or "")
        for check in manifest["events"][event]["checks"]
    }

    failures: list[str] = []
    for relative_script, (
        matcher,
        timeout,
        argv_suffix,
    ) in REQUIRED_STANDALONE_HANDLERS[event].items():
        script = HOOKS_ROOT / relative_script
        if _norm(relative_script) in manifest_scripts:
            failures.append(
                f"{relative_script} is incorrectly folded into the inject-only dispatcher"
            )
            continue

        matches = _commands_referencing(settings, script, event)
        if len(matches) != 1:
            failures.append(
                f"{relative_script} needs exactly one standalone hooks.{event} entry; "
                f"found {len(matches)}"
            )
            continue

        _event, group, hook = matches[0]
        if not _matcher_equivalent(group.get("matcher"), matcher):
            failures.append(
                f"{relative_script} matcher is {group.get('matcher')!r}, expected {matcher!r}"
            )
        if hook.get("timeout") != timeout:
            failures.append(
                f"{relative_script} timeout is {hook.get('timeout')!r}, expected {timeout}"
            )
        command = str(hook.get("command") or "").strip()
        if argv_suffix and not command.endswith(f" {argv_suffix}"):
            failures.append(
                f"{relative_script} command must end with {argv_suffix!r}: {command!r}"
            )

    assert not failures, "standalone hook-contract regressions:\n" + "\n".join(failures)


def test_prepost_manifest_scripts_have_no_standalone_duplicates():
    manifest = _load(MANIFEST)
    scripts = {
        (_norm(check["script"]), event): check["script"]
        for event in ("PreToolUse", "PostToolUse")
        for check in manifest["events"][event]["checks"]
    }

    failures: list[str] = []
    for label, path in (("settings.json", SETTINGS), ("hooks.json", HOOKS_JSON)):
        document = _load(path)
        for event, _group, hook in _hook_entries(document):
            command = _norm(str(hook.get("command") or ""))
            for (script_norm, manifest_event), script in scripts.items():
                if event == manifest_event and script_norm in command:
                    failures.append(
                        f"{label}:{event} duplicates {script}: {hook['command']}"
                    )

    assert not failures, "manifest scripts must not also run standalone:\n" + "\n".join(
        failures
    )


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__, "-q"]))
