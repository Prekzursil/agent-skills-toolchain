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
AGENT_SELF_HOOKS_JSON = CLAUDE_ROOT / "agent-self" / "config" / "hooks" / "hooks.json"
KNOWN_BROKEN_HOOKS_JSON = (
    HOOKS_ROOT / "_fleet-backups" / "20260713-WU-A" / "hooks.json.before"
)
QUALITY_WORKFLOW = CLAUDE_ROOT / ".github" / "workflows" / "quality.yml"
DISPATCH = HERE / "dispatch.py"
NO_FORCE_PUSH = HOOKS_ROOT / "no-force-push" / "hook.py"

HOOK_MANIFEST_CONSUMERS = (
    ("repo plugin surface", HOOKS_JSON),
    ("agent-self deploy surface", AGENT_SELF_HOOKS_JSON),
)
CROSS_CONSUMER_TOP_LEVEL_KEYS = frozenset({"description", "hooks"})
MINIMUM_CONFORMING_COMMAND_HOOKS = 7
CONFORMANCE_CI_MARKER = (
    "run: python -m pytest hooks/_dispatch/test_wiring.py -q "
    "-k hook_manifest_conformance"
)

DISPATCH_EVENTS = {
    "SessionStart": "sessionstart",
    "PreToolUse": "pretooluse",
    "PostToolUse": "posttooluse",
    "Stop": "stop",
}

# ENV-DEP GATE.  ``SETTINGS`` resolves to ``<CLAUDE_ROOT>/settings.json``, i.e. the
# DEPLOYED ``~/.claude/settings.json``.  That document is machine-local user
# configuration (env, enabledPlugins, deniedMcpServers, the live hook wiring); it is
# deliberately untracked and therefore never exists in a plain repo checkout or on a
# CI runner -- every assertion below that reads it died with FileNotFoundError there,
# which is why quality.yml had to --ignore this whole module.  The skip is keyed on the
# FILE, not on the platform, so the checks still RUN and still enforce the live wiring
# when this suite is executed from its deployed location under ~/.claude/hooks/.
LIVE_SETTINGS_AVAILABLE = SETTINGS.is_file()
requires_live_settings = pytest.mark.skipif(
    not LIVE_SETTINGS_AVAILABLE,
    reason=(
        f"needs the deployed live {SETTINGS.name!r} at {SETTINGS.parent}; it is "
        "machine-local, untracked user configuration that never exists in a repo "
        "checkout or on CI. Run this suite from ~/.claude/hooks/_dispatch/ to enforce it."
    ),
)

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
        # Extended beyond Bash to the browser rail so oversized base64 screenshots
        # (Playwright / claude-in-chrome / chrome-devtools) are dropped to a temp
        # file instead of flooding context. Mirror this in the live settings.json.
        "cmd-rewrite/compress-output.py": (
            "Bash|mcp__playwright__.*|mcp__claude-in-chrome__.*|mcp__chrome-devtools__.*",
            10,
            "",
        ),
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


def _conforming_command_hook_count(document: dict) -> int:
    """Return command hooks visible to every supported manifest consumer."""

    if set(document).difference(CROSS_CONSUMER_TOP_LEVEL_KEYS):
        return 0
    return sum(1 for _ in _hook_entries(document))


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


@requires_live_settings
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


@requires_live_settings
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

    # ``hooks_root`` records the absolute DEPLOY root the dispatcher uses at runtime
    # ("C:/Users/.../.claude/hooks").  Resolving THIS manifest's entries against that
    # foreign path checks a different tree than the one the manifest ships in, and on a
    # non-Windows checkout it is not even a path that exists, so every entry read as
    # "missing".  Prefer the recorded root only while it really is a directory (keeps the
    # deployed behaviour byte-identical), otherwise fall back to the tree this manifest
    # lives in -- the same fallback dispatch.py:240 already applies.
    recorded_root = Path(manifest.get("hooks_root") or HOOKS_ROOT)
    root = recorded_root if recorded_root.is_dir() else HOOKS_ROOT
    for check in checks:
        script = check.get("script")
        assert isinstance(script, str) and script.strip(), (
            f"events.{event} check {check.get('name')!r} must name a script"
        )
        assert (root / script).is_file(), (
            f"events.{event} check {check.get('name')!r} points to missing {root / script}"
        )


# D-wu-49.  This census used to be ONE ``xfail(strict=True)`` per EVENT covering all seven
# absent handlers at once, so restoring a single handler left the parameter still failing
# (six others still missing) and therefore STILL reported as a clean ``xfailed``.  The gate
# could not prove an individual repair -- measured on anti-degen/fingerprint, whose script
# exists in both trees while the manifest carries only three PostToolUse checks.  It is now
# parametrised PER HANDLER, with the strict marker applied only to the ones known-absent
# below, so restoring exactly one flips ITS case to XPASS -> strict failure -> the entry
# must be removed from this allowlist in the same commit.  Nothing is restored here: the
# marker text is explicit that whether each handler is genuinely-lost functionality or an
# orphan duplicate of the ~/.agents harness is UNRESOLVED and must be settled per hook.
KNOWN_UNREGISTERED_HANDLERS = {
    "PreToolUse": frozenset(
        {
            "goal-reinject/reinject",
            "compchem-preflight",
            "strong-tool-nudge",
            "mcp-liveness/pretool",
            "edit-checkpoints",
            "contraindication",
            "iatrogenics",
        }
    ),
    "PostToolUse": frozenset(
        {
            "anti-degen/fingerprint",
            "claim-guard/ledger-write",
            "memory-guard/scan",
            "edit-validate/record",
            "fresh-verify/trigger",
            "orphan-commit",
            "semantic-router/observe",
        }
    ),
}

CENSUS_XFAIL_REASON = (
    "RED FROM BIRTH IN THIS REPO, and still red: the 14 dispatcher-compatible "
    "handlers (7 PreToolUse: goal-reinject/reinject, compchem-preflight, "
    "strong-tool-nudge, mcp-liveness/pretool, edit-checkpoints, contraindication, "
    "iatrogenics; 7 PostToolUse: anti-degen/fingerprint, claim-guard/ledger-write, "
    "memory-guard/scan, edit-validate/record, fresh-verify/trigger, orphan-commit, "
    "semantic-router/observe) are absent from events.*.checks here. "
    "PROVENANCE -- do NOT search repo history, nothing was ever dropped there: all 8 "
    "commits that have ever touched this manifest contain 0 of the 14 names and its "
    "check counts only ever GREW (Pre 3->4->5, Post 3). This census arrived AHEAD of "
    "the manifest, at faae06d ('rescue 1,756 orphaned harness files'), whose tree "
    "carried Pre=4/Post=3 -- which is why the assertion has never passed in a "
    "checkout. What genuinely lost the handlers is the LIVE DEPLOYED "
    "~/.claude/hooks/_dispatch/manifest.json: its sibling backup "
    "manifest.json.bak-20260714-012512 still carries all 14 (Pre=10/Post=12), so "
    "recover the exact entries from that .bak, not from git. "
    "IMPACT -- per-hook and UNRESOLVED, deliberately not overstated: all 14 scripts "
    "still exist on disk in both trees and are registered in NO ~/.claude surface "
    "(0 hits for all 14 in the live settings.json; detector controlled -- "
    "no-force-push/hook.py and _dispatch/dispatch.py both hit in the same walk), so "
    "nothing under ~/.claude runs them. That is NOT the same as 14 broken live "
    "mechanisms. goal-reinject/reinject.py is a MEASURED orphan duplicate: goal "
    "re-injection (AGENTS.md section 2) is live and running, owned by the ~/.agents "
    "harness -- ~/.agents/harness/dispatcher.py is PreToolUse hook #1 in the live "
    "settings.json and its ~/.agents/state/harness/session-goals/ state is written "
    "during ordinary tool use. Whether each of the other 13 is genuinely-lost "
    "functionality or likewise an orphan duplicate is NOT established; settle it per "
    "hook before restoring anything. "
    "SCOPE OF THIS MARKER: it guards ONLY the census assertion below. The routing "
    "contract lives in test_prepost_manifest_routes_match_dispatch_contract, which is "
    "deliberately UNMARKED. While one strict xfail spanned both assertions it absorbed "
    "every routing regression, because the census can never pass while these 14 are "
    "missing, so ANY route failure still satisfied the marker: measured, corrupting "
    "the matcher of dup-guard -- a handler PRESENT here today -- left the suite at "
    "exit 0, byte-identical to green. Never put the two back under one marker. "
    "PER-HANDLER SCOPE (D-wu-49): this marker is now applied to ONE handler at a time, "
    "so restoring that handler alone turns its case XPASS and, being strict, RED -- the "
    "gate can finally prove an individual repair instead of absorbing it."
)


def _census_params() -> list[pytest.ParameterSet]:
    """One parameter per (event, handler), strict-xfailed only where known-absent."""

    params: list[pytest.ParameterSet] = []
    for event, expected in EXPECTED_DISPATCH_CHECKS.items():
        for name in expected:
            marks = (
                (pytest.mark.xfail(strict=True, reason=CENSUS_XFAIL_REASON),)
                if name in KNOWN_UNREGISTERED_HANDLERS[event]
                else ()
            )
            params.append(pytest.param(event, name, marks=marks, id=f"{event}-{name}"))
    return params


def test_known_unregistered_allowlist_names_only_census_handlers():
    """The allowlist may not carry a name the census does not expect.

    Without this, a typo'd or stale entry would silently exempt nothing (or worse, keep
    exempting a handler after it was dropped from the census) and the per-handler marker
    would be reported as passing while guarding an empty set.
    """

    stale = {
        (event, name)
        for event, names in KNOWN_UNREGISTERED_HANDLERS.items()
        for name in names
        if name not in EXPECTED_DISPATCH_CHECKS[event]
    }
    assert not stale, f"KNOWN_UNREGISTERED_HANDLERS names non-census handlers: {stale}"


def test_known_unregistered_allowlist_matches_the_manifest():
    """The allowlist may not claim a handler is absent while the manifest registers it.

    This is the maintenance contract the per-handler marker creates, made ACTIONABLE.
    Without it, wiring a handler still turns its strict-xfail case XPASS and the suite
    still goes red -- but the only diagnostic is pytest's bare ``[XPASS(strict)]``, which
    says nothing about what to do.  A reader then reasonably suspects the wiring is
    wrong, when in fact the wiring is the POINT and this list is what is stale.

    Concrete case this exists for, measured rather than assumed: on this base
    ``hooks/_dispatch/manifest.json`` registers PreToolUse = [bg-registry/register,
    memory-spool/spool, dup-guard, monitor-autolaunch, codex-monitor-autolaunch] and
    PostToolUse = [memory-spool/flush_check, tool-result-sentinel, stub-ledger/record],
    so every allowlisted name is genuinely absent and the marker is honest.  An
    in-flight branch elsewhere wires ``edit-checkpoints`` (PreToolUse) and
    ``claim-guard/ledger-write`` (PostToolUse); when it merges, THIS test fails first
    and names both entries, instead of two opaque XPASSes.

    The fix is always the same and is never "weaken the census": delete the restored
    name from KNOWN_UNREGISTERED_HANDLERS in the same commit that wires it.
    """

    registered = {
        event: {
            check.get("name") for check in _load(MANIFEST)["events"][event]["checks"]
        }
        for event in KNOWN_UNREGISTERED_HANDLERS
    }
    contradicted = sorted(
        f"{event}:{name}"
        for event, names in KNOWN_UNREGISTERED_HANDLERS.items()
        for name in names
        if name in registered[event]
    )
    assert not contradicted, (
        "KNOWN_UNREGISTERED_HANDLERS still lists handlers the manifest now registers: "
        f"{contradicted}. They were wired -- that is the outcome this census exists to "
        "detect. Remove them from the allowlist (do NOT relax the census); their "
        "strict-xfail cases then become ordinary passing assertions."
    )


@pytest.mark.parametrize(("event", "name"), _census_params())
def test_prepost_manifest_contains_every_dispatch_compatible_handler(
    event: str, name: str
):
    """CENSUS ONLY -- is this dispatcher-compatible handler registered at all?

    Kept separate from the routing contract on purpose.  While both assertions shared one
    ``xfail(strict=True)`` this census could never pass, so any route failure also
    satisfied the marker and was reported as a clean ``xfailed`` -- including one on a
    handler that is present today.  It is also parametrised PER HANDLER rather than per
    event, so a single restoration is independently detectable (D-wu-49).
    """

    actual = {
        check.get("name"): check.get("script")
        for check in _load(MANIFEST)["events"][event]["checks"]
    }
    expected_script = EXPECTED_DISPATCH_CHECKS[event][name]

    assert actual.get(name) == expected_script, (
        f"events.{event} is missing dispatcher-compatible Tier-1.1 handler "
        f"{name!r} -> {expected_script!r}"
    )


@pytest.mark.parametrize("event", ("PreToolUse", "PostToolUse"))
def test_prepost_manifest_routes_match_dispatch_contract(event: str):
    """ROUTING ONLY, and deliberately NOT xfailed.

    Scoped to the handlers actually PRESENT in the manifest, so it is enforceable today
    against the entries that survive and turns RED the moment an absent one is restored
    with the wrong matcher/timeout/args/emits.  ``compared`` guards against the check
    silently degrading to a vacuous pass if every expected name disappears at once.
    """

    checks = _load(MANIFEST)["events"][event]["checks"]

    compared = 0
    route_failures: list[str] = []
    for name, (args, matcher, timeout, emits) in EXPECTED_DISPATCH_ROUTES[
        event
    ].items():
        check = next((item for item in checks if item.get("name") == name), None)
        if check is None:
            continue
        compared += 1
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
    assert compared, (
        f"events.{event} contains none of the {len(EXPECTED_DISPATCH_ROUTES[event])} "
        "routed handlers, so this contract checked nothing"
    )


@requires_live_settings
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

    # Each registration document is optional and the two surfaces do not co-exist:
    # settings.json is the untracked live deployment (absent in a checkout/CI) while
    # hooks.json is the tracked plugin surface (absent from the live ~/.claude deploy).
    # Scan whichever are present rather than dying on the other -- skipping outright
    # would drop the CI-checkable hooks.json half. Presence itself is asserted
    # elsewhere: test_hook_manifest_conformance_gate_is_adopted loads HOOKS_JSON.
    available = [
        (label, path)
        for label, path in (("settings.json", SETTINGS), ("hooks.json", HOOKS_JSON))
        if path.is_file()
    ]
    if not available:
        pytest.skip("neither settings.json nor hooks.json is present to scan")

    failures: list[str] = []
    for label, path in available:
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


def test_hook_manifest_conformance_gate_is_adopted():
    """Known-broken: pre-B03 quality.yml never invokes this conformance gate."""

    consumer_paths = {path for _surface, path in HOOK_MANIFEST_CONSUMERS}
    assert len(consumer_paths) >= 2, (
        "cross-consumer gate must exercise at least two manifest surfaces"
    )
    for surface, path in HOOK_MANIFEST_CONSUMERS:
        count = _conforming_command_hook_count(_load(path))
        assert count >= MINIMUM_CONFORMING_COMMAND_HOOKS, (
            f"{surface} must load at least {MINIMUM_CONFORMING_COMMAND_HOOKS} "
            f"command hooks; loaded {count}"
        )

    known_broken = _load(KNOWN_BROKEN_HOOKS_JSON)
    assert "$schema" in known_broken, (
        "known-broken control lost its discriminating field"
    )
    assert _conforming_command_hook_count(known_broken) == 0, (
        "detector must reproduce the historical unknown-key zero-hook failure"
    )

    workflow_lines = {
        line.strip()
        for line in QUALITY_WORKFLOW.read_text(encoding="utf-8").splitlines()
    }
    assert CONFORMANCE_CI_MARKER in workflow_lines, (
        "quality CI must invoke the manifest conformance tests explicitly"
    )
