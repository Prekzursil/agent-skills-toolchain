#!/usr/bin/env python3
"""Regression tests for the live local-hook dispatcher registrations.

These tests intentionally inspect both registration documents.  ``settings.json``
is the active user-level wire, while ``hooks/hooks.json`` is also checked so a
future plugin/manual registration cannot silently reintroduce one of the Python
hooks already consolidated behind ``_dispatch``.
"""

from __future__ import annotations

import importlib.util
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
# The TRACKED deploy mirror of the live settings (agent-self/README.md; deployed by
# agent-self/bootstrap.ps1). Unlike SETTINGS above it exists in every checkout and on CI, so
# assertions against it are not gated behind requires_live_settings.
TRACKED_DEPLOY_SETTINGS = CLAUDE_ROOT / "agent-self" / "config" / "settings.json"
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


def _sample_tool_name(alternative: str) -> str:
    """A concrete tool_name that the given matcher ALTERNATIVE is meant to admit.

    ``mcp__basic-memory__.*`` -> ``mcp__basic-memory__x``; a literal alternative is itself.
    """

    return re.sub(r"\.\*|\.\+", "x", alternative)


@pytest.mark.parametrize("event,token", DISPATCH_EVENTS.items())
def test_tracked_deploy_mirror_admits_every_dispatched_route(event: str, token: str):
    """A087: the TRACKED deploy mirror must not silently prefilter a manifest route away.

    ``test_settings_has_exactly_one_local_dispatch_for_event`` above enforces the same mirror
    invariant, but only against the DEPLOYED ``~/.claude/settings.json`` -- machine-local and
    untracked, so ``requires_live_settings`` skips it in every checkout and on every CI runner.
    ``agent-self/config/settings.json`` IS tracked and IS what ``agent-self/bootstrap.ps1``
    deploys, so this assertion is checkable here and closes the detector hole.

    Measured at 27fb388: the mirror's PreToolUse dispatcher matcher was
    ``Task|Bash|PowerShell|Edit|Write|MultiEdit|mcp__basic-memory__.*|mcp__schrodinger__glide_dock``
    ``|mcp__schrodinger__prime_mmgbsa|mcp__cheatengine__.*|mcp__frida-mcp__.*`` -- no
    ``Workflow`` and no ``mcp__codex__codex``, so the registry-driven ``monitor-autolaunch``
    check (matcher ``Task|Workflow|mcp__codex__codex``) could only ever be reached through
    ``Task``.  A ``Workflow`` tool call never started the dispatcher at all, while the
    superseded standalone ``workflow-monitor-autolaunch`` group ran in its place and ignores
    the per-monitor ``MONITOR_AUTOLAUNCH_WFMON`` opt-out the successor honours.

    The second assertion is the one that actually catches this class: string equality alone
    would pass on any two matching-but-wrong values, so every inner check matcher's
    alternatives are re-derived and required to survive the outer prefilter.
    """

    settings = _load(TRACKED_DEPLOY_SETTINGS)
    # RELATIVE needle, deliberately.  The mirror records the DEPLOY root
    # (C:/Users/<user>/.claude/hooks/...), which never equals this checkout's absolute
    # DISPATCH path -- matching on the absolute path made this assertion report "found 0" in
    # BOTH the broken and the fixed state, i.e. it measured nothing.
    matches = _commands_referencing(settings, DISPATCH.relative_to(HOOKS_ROOT), event)
    assert len(matches) == 1, (
        f"the tracked deploy mirror must carry exactly one hooks.{event} local dispatch "
        f"command; found {len(matches)}"
    )
    _event, group, hook = matches[0]
    command = str(hook.get("command") or "").strip()
    assert re.search(rf"(?:^|\s){re.escape(token)}\s*$", command, re.IGNORECASE), (
        f"hooks.{event} dispatcher must receive the {token!r} event token: {command!r}"
    )

    manifest_event = _load(MANIFEST)["events"][event]
    expected_matcher = manifest_event.get("settings_matcher")
    actual_matcher = group.get("matcher")
    if expected_matcher is None:
        assert actual_matcher is None, (
            f"hooks.{event} declares no settings_matcher; the mirror must not add one "
            f"({actual_matcher!r})"
        )
    elif expected_matcher == "*":
        assert actual_matcher in {"*", ".*"}, (
            f"hooks.{event} must match every event subtype, got {actual_matcher!r}"
        )
    else:
        assert actual_matcher == expected_matcher, (
            f"hooks.{event} mirror matcher {actual_matcher!r} does not mirror manifest "
            f"settings_matcher {expected_matcher!r}"
        )
    assert hook.get("timeout", 0) >= manifest_event["settings_timeout"], (
        f"hooks.{event} mirror timeout must cover the manifest's dispatcher budget"
    )

    # No dead routes: every tool a manifest check claims must clear the outer prefilter.
    outer = actual_matcher if isinstance(actual_matcher, str) else ".*"
    if outer == "*":
        outer = ".*"
    checked = 0
    dead: list[str] = []
    for check in manifest_event.get("checks") or []:
        inner = check.get("matcher")
        if not isinstance(inner, str) or not inner:
            continue  # unconditional check: the outer matcher decides on its own
        for alternative in inner.split("|"):
            if not alternative:
                continue
            checked += 1
            sample = _sample_tool_name(alternative)
            if not re.fullmatch(outer, sample):
                dead.append(f"{check.get('name')} needs {alternative!r} ({sample!r})")
    assert not dead, (
        f"hooks.{event} prefilter {outer!r} silently suppresses manifest routes:\n"
        + "\n".join(dead)
    )
    if event == "PreToolUse":
        assert checked, (
            "PreToolUse carries matcher-scoped checks, so a zero here means this "
            "assertion degraded to a vacuous pass"
        )


def _dispatch_module():
    """Import the PRODUCTION dispatcher (stdlib-only at module level)."""

    spec = importlib.util.spec_from_file_location("dispatch_under_test", DISPATCH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_bash_posttooluse_reaches_the_claim_ledger_writer():
    """D011: a Bash PostToolUse event must select ``claim-guard/ledger-write``.

    Runs the PRODUCTION selector (``dispatch._select``), never a re-implementation, and
    carries its own positive control: ``tool-result-sentinel`` (matcher ``.*``) must be
    selected for the SAME input, so a selector that silently matched nothing could not
    make this assertion pass vacuously.

    CONSUMER-LIVENESS half.  The writer is not a write-only orphan: it appends the
    per-session Bash-exit ledger under ``CLAIM_GUARD_LEDGER_ROOT``
    (claim-guard/ledger-write.py:39-44, :195-197) and ``journey-coverage/check.py:36-41``
    reads exactly that root while already being wired under ``events.Stop.checks``.  While
    the producer was absent that live Stop gate ran every turn against an empty ledger and
    could never see a journey as covered.  Both halves are asserted here so re-orphaning
    EITHER side turns this red.
    """

    dispatch = _dispatch_module()
    manifest = _load(MANIFEST)
    checks = manifest["events"]["PostToolUse"]["checks"]

    selected = [check.get("name") for check in dispatch._select(checks, "Bash")]
    assert "tool-result-sentinel" in selected, (
        "positive control: the '.*' sentinel must select for Bash; without it a broken "
        f"selector would satisfy this test vacuously (selected={selected})"
    )
    assert "claim-guard/ledger-write" in selected, (
        "a Bash PostToolUse event must reach the claim-guard ledger writer, otherwise "
        f"no command/exit record is ever appended (selected={selected})"
    )
    assert "claim-guard/ledger-write" not in [
        check.get("name") for check in dispatch._select(checks, "Read")
    ], "the ledger writer must stay Bash-scoped, not run on every tool"

    stop_names = {check.get("name") for check in manifest["events"]["Stop"]["checks"]}
    assert "journey-coverage" in stop_names, (
        "the ledger's live consumer must stay wired, or the writer becomes write-only"
    )
    writer = (HOOKS_ROOT / "claim-guard" / "ledger-write.py").read_text(
        encoding="utf-8"
    )
    reader = (HOOKS_ROOT / "journey-coverage" / "check.py").read_text(encoding="utf-8")
    assert (
        "CLAIM_GUARD_LEDGER_ROOT" in writer and "CLAIM_GUARD_LEDGER_ROOT" in reader
    ), "producer and consumer must keep naming the same ledger root"


@pytest.mark.xfail(
    strict=True,
    reason=(
        "RED FROM BIRTH IN THIS REPO, and still red: the 13 dispatcher-compatible "
        "handlers (7 PreToolUse: goal-reinject/reinject, compchem-preflight, "
        "strong-tool-nudge, mcp-liveness/pretool, edit-checkpoints, contraindication, "
        "iatrogenics; 6 PostToolUse: anti-degen/fingerprint, "
        "memory-guard/scan, edit-validate/record, fresh-verify/trigger, orphan-commit, "
        "semantic-router/observe) are absent from events.*.checks here. "
        "SCOPE CORRECTION 2 -- COUNTED, not paraphrased: 3 of the 13 named above are "
        "now PRESENT in the manifest (PreToolUse mcp-liveness/pretool and "
        "edit-checkpoints, PostToolUse edit-validate/record) and exactly 10 remain "
        "absent, so this marker still holds. Each restoration carried its own per-hook "
        "adjudication, which is what this reason demands: edit-checkpoints has a live "
        "consumer contract in commands/rollback.md and no duplicate owner; "
        "mcp-liveness/pretool performs the real basic-memory `initialize` handshake "
        "that the already-wired heartbeat/heartbeat.py explicitly does NOT do. The "
        "wording is corrected here rather than deleted so the count is not re-derived "
        "wrong -- and the restorations are pinned by their own UNMARKED tests, not by "
        "this census, which can never pass while any of the remaining 10 is absent and "
        "therefore protects no single restoration. "
        "SCOPE CORRECTION -- this list said 14 and included claim-guard/ledger-write "
        "under PostToolUse. That entry is now PRESENT in the manifest: it is the only "
        "writer of the Bash-exit ledger that the already-wired Stop consumer "
        "journey-coverage/check.py:14-16,144-162 reads, so while it was unregistered "
        "every done-claim reported a just-passed journey as 'never run'. The earlier "
        "wording is corrected here rather than deleted so the count is not re-derived "
        "wrong; the remaining 13 are still absent and this marker still holds. "
        "PROVENANCE -- do NOT search repo history, nothing was ever dropped there: all 8 "
        "commits that had touched this manifest before that restoration contain 0 of the "
        "14 names and its check counts only ever GREW (Pre 3->4->5, Post 3->4). This "
        "census arrived AHEAD of "
        "the manifest, at faae06d ('rescue 1,756 orphaned harness files'), whose tree "
        "carried Pre=4/Post=3 -- which is why the assertion has never passed in a "
        "checkout. What genuinely lost the handlers is the LIVE DEPLOYED "
        "~/.claude/hooks/_dispatch/manifest.json: its sibling backup "
        "manifest.json.bak-20260714-012512 still carries all 14 (Pre=10/Post=12), so "
        "recover the exact entries from that .bak, not from git. "
        "IMPACT -- per-hook and UNRESOLVED, deliberately not overstated: all 13 scripts "
        "still exist on disk in both trees and are registered in NO ~/.claude surface "
        "(0 hits for all 13 in the live settings.json; detector controlled -- "
        "no-force-push/hook.py and _dispatch/dispatch.py both hit in the same walk), so "
        "nothing under ~/.claude runs them. That is NOT the same as 14 broken live "
        "mechanisms. goal-reinject/reinject.py is a MEASURED orphan duplicate: goal "
        "re-injection (AGENTS.md section 2) is live and running, owned by the ~/.agents "
        "harness -- ~/.agents/harness/dispatcher.py is PreToolUse hook #1 in the live "
        "settings.json and its ~/.agents/state/harness/session-goals/ state is written "
        "during ordinary tool use. Whether each of the other 12 is genuinely-lost "
        "functionality or likewise an orphan duplicate is NOT established; settle it per "
        "hook before restoring anything. "
        "SCOPE OF THIS MARKER: it guards ONLY the census assertion below. The routing "
        "contract lives in test_prepost_manifest_routes_match_dispatch_contract, which is "
        "deliberately UNMARKED. While one strict xfail spanned both assertions it absorbed "
        "every routing regression, because the census can never pass while these 13 are "
        "missing, so ANY route failure still satisfied the marker: measured, corrupting "
        "the matcher of dup-guard -- a handler PRESENT here today -- left the suite at "
        "exit 0, byte-identical to green. Never put the two back under one marker."
    ),
)
@pytest.mark.parametrize("event", ("PreToolUse", "PostToolUse"))
def test_prepost_manifest_contains_every_dispatch_compatible_handler(event: str):
    """CENSUS ONLY -- is every dispatcher-compatible handler registered at all?

    Kept separate from the routing contract on purpose.  While both assertions shared one
    ``xfail(strict=True)`` this census could never pass, so any route failure also
    satisfied the marker and was reported as a clean ``xfailed`` -- including one on a
    handler that is present today.
    """

    actual = {
        check.get("name"): check.get("script")
        for check in _load(MANIFEST)["events"][event]["checks"]
    }
    expected = EXPECTED_DISPATCH_CHECKS[event]

    missing = {
        name: script for name, script in expected.items() if actual.get(name) != script
    }
    assert not missing, (
        f"events.{event} is missing dispatcher-compatible Tier-1.1 handlers: {missing}"
    )


def test_mcp_liveness_pretool_is_actually_dispatched():
    """C33 D-a094, re-derived: the basic-memory liveness handshake ran nowhere.

    ``EXPECTED_DISPATCH_CHECKS``/``EXPECTED_DISPATCH_ROUTES`` above have required
    ``mcp-liveness/pretool`` since this census was written, but it was absent from
    ``events.PreToolUse.checks``, so every ``mcp__basic-memory__*`` call proceeded
    with no liveness handshake at all.

    Settled per-hook, which is exactly what the strict-xfail census below demands
    before anything is restored: this is NOT an orphan duplicate.
    ``heartbeat/heartbeat.py`` (already wired at SessionStart and Stop) performs only
    a TCP connect and says in its own words that the real ``initialize`` handshake is
    the PreToolUse liveness hook's job -- so this is genuinely-lost functionality.
    It is also inject-only: ``liveness.run()`` returns 0 on every path and speaks
    solely through ``emit()``, so consolidating it loses nothing.

    Scoped deliberately to ONE handler. The other 12 still need the same individual
    adjudication and this test does not claim otherwise.
    """
    checks = _load(MANIFEST)["events"]["PreToolUse"]["checks"]
    entry = next(
        (c for c in checks if c.get("name") == "mcp-liveness/pretool"),
        None,
    )
    assert entry is not None, (
        "mcp-liveness/pretool is required by EXPECTED_DISPATCH_CHECKS/ROUTES but is "
        "absent from events.PreToolUse.checks -- basic-memory calls run with no "
        "liveness handshake"
    )
    assert entry.get("script") == "mcp-liveness/liveness.py"
    assert entry.get("args") == ["pretool"], (
        "without the 'pretool' argv the module defaults to sessionstart mode"
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
