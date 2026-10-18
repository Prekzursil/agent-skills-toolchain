#!/usr/bin/env python3
r"""deploy_dispatch_wiring.py — surgical, idempotent deploy of the _dispatch hook WIRING.

WHY THIS EXISTS (bug WF-2). ``hooks/_dispatch/manifest.json`` DECLARES which tools must reach
the dispatcher (``events.<Event>.settings_matcher``) and which per-hook checks it then runs. The
tracked mirror ``agent-self/config/settings.json`` matches that declaration and is gated by
``hooks/_dispatch/test_wiring.py::test_tracked_deploy_mirror_admits_every_dispatched_route``
(A087). The DEPLOYED ``~/.claude/settings.json`` is machine-local and untracked, so nothing
carries the declaration across the last hop -- and measured 2026-08-17/18 it had drifted: its
PreToolUse dispatcher matcher omitted ``Workflow``, while a superseded standalone
``workflow-monitor-autolaunch`` group served that trigger instead. Consequence: the generalized
``monitor-autolaunch`` check was UNREACHABLE for ``Workflow`` on this box, and the legacy hook it
replaced ignores the per-monitor ``MONITOR_AUTOLAUNCH_WFMON`` opt-out the successor honours.

WHY NOT ``bootstrap.ps1``. Its step 3 is a wholesale ``Copy-Item config\* -> ~/.claude -Recurse
-Force``, which REPLACES the live settings.json outright. Measured on this box before writing
this tool, the live file carries machine-local keys the tracked mirror does not: an ``env`` entry
holding a live API credential, and a ``model`` pin, plus a ``SessionEnd`` hook group absent from
the mirror. A wholesale copy destroys all three. AGENTS.md section 9 forbids an agent modifying a
credential, so a vehicle that silently deletes one is not usable for this fix.

WHAT THIS DOES INSTEAD. It reads the manifest that sits BESIDE the deployed dispatcher (so the
declaration and the thing being wired can never disagree about which tree they describe) and
rewrites ONLY:
  1. the ``matcher`` of the single settings group whose command is that dispatcher, per event; and
  2. removes settings groups that run a SUPERSEDED standalone hook whose route the dispatcher now
     owns (``SUPERSEDED_STANDALONE`` below).
Both land in ONE atomic write. Doing them separately is the trap WF-2 names explicitly: admitting
``Workflow`` at the dispatcher while the legacy group is still wired fires BOTH launchers, whose
lock namespaces differ, so a second tab is guaranteed. Every other byte of settings.json is
preserved -- ``env``, ``model``, ``permissions``, ``enabledPlugins``, every other event.

FAIL-CLOSED. Missing settings, missing manifest, unparseable JSON, no dispatcher group for a
declared event, or a superseded removal whose successor the manifest does NOT declare -> non-zero
exit and no write. An empty plan is reported as already-in-sync, never inferred from a failed scan.

NEVER PRINTS SETTINGS CONTENT. The live file holds a credential; this tool reports matcher strings
and group indices only.

USAGE
    python agent-self/deploy_dispatch_wiring.py                 # dry run: print the plan
    python agent-self/deploy_dispatch_wiring.py --apply         # back up, then atomic write
    python agent-self/deploy_dispatch_wiring.py --claude-root D # operate on another root (tests)
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
from pathlib import Path

#: ``<claude-root>/hooks/_dispatch/dispatch.py <token>`` is the dispatcher command per event.
DISPATCH_RELPATH = "_dispatch/dispatch.py"

#: Standalone hooks whose trigger a manifest check has TAKEN OVER, per event.  Mapping is
#: ``legacy script relpath -> the manifest check script that supersedes it``.  The successor must
#: actually be declared in the manifest for that event or the removal is refused (fail-closed):
#: dropping the legacy group while nothing replaced it would silently retire the monitor.
SUPERSEDED_STANDALONE: dict[str, dict[str, str]] = {
    "PreToolUse": {
        # WF-2: the registry-driven successor (matcher ``Task|Workflow|mcp__codex__codex``)
        # replaces the wfmon-only legacy hook.  Deliberately NOT listing
        # ``codex-monitor-autolaunch/check.py``: the manifest runs it on ``Bash|PowerShell`` for
        # CLI ``codex exec`` text, while its standalone group carries ``mcp__codex__codex``, a
        # tool its own ``_is_codex_launch`` returns False for.  Those are disjoint routes that
        # the repo mirror keeps on purpose, not a supersession.
        "workflow-monitor-autolaunch/check.py": "monitor-autolaunch/check.py",
        # 2026-10-18 review thread "remove superseded guards during surgical
        # deployment": the six PreToolUse guards the blocking-mode wave
        # consolidated as exec-mode manifest checks.  On an install deployed
        # BEFORE that wave the standalone groups are still wired; widening the
        # dispatcher matcher alone would run BOTH copies on every overlapping
        # call (double scans, racing side effects on stateful hooks such as
        # loop-recovery).  Each successor below IS the same script, now reached
        # behind the dispatcher with its real exit code / decision JSON
        # propagated (dispatch.py exec mode; pinned by test_blocking_mode.py),
        # so the standalone copy is a double-run, not extra safety.
        # ``estate-deny-guard.py`` is deliberately NOT listed: it never had a
        # standalone settings entry on the tracked-mirror deploy path (it was
        # bridged live-only via the manifest's owner-reviewed ``exec_path``).
        "no-force-push/hook.py": "no-force-push/hook.py",
        "test-tamper-guard/guard.py": "test-tamper-guard/guard.py",
        "cmd-rewrite/inject-nopager.py": "cmd-rewrite/inject-nopager.py",
        "ulysses/enforce.py": "ulysses/enforce.py",
        "loop-recovery/handler.py": "loop-recovery/handler.py",
        "deny-credential-reads/deny.py": "deny-credential-reads/deny.py",
    },
}


class WiringError(RuntimeError):
    """Fail-closed condition: report and exit non-zero without writing."""


def _load_json(path: Path) -> dict:
    if not path.is_file():
        raise WiringError(f"required file missing: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise WiringError(f"unreadable JSON at {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise WiringError(f"{path} must hold a JSON object")
    return data


def _norm(value: str) -> str:
    return str(value).replace("\\", "/").casefold()


def references(command: str, relpath: str) -> bool:
    """True iff ``command`` runs the hook at ``relpath``, matched on a PATH-SEGMENT boundary.

    A bare substring test is wrong here and the collision is live, not hypothetical:
    ``codex-monitor-autolaunch/check.py`` CONTAINS ``monitor-autolaunch/check.py``, so a naive
    ``needle in haystack`` reports the codex hook as the wfmon hook and would delete a wiring this
    tool must never touch.  Requiring the character before the match to be ``/`` (or the match to
    start the string) rejects that.
    """

    hay, needle = _norm(command), _norm(relpath)
    start = 0
    while True:
        idx = hay.find(needle, start)
        if idx < 0:
            return False
        if idx == 0 or hay[idx - 1] == "/":
            return True
        start = idx + 1


def matcher_satisfies(actual: object, expected: str) -> bool:
    """True iff ``actual`` already means what the manifest's ``settings_matcher`` declares.

    A declared ``"*"`` (every subtype) is satisfied by EITHER spelling, ``"*"`` or ``".*"`` --
    the same equivalence ``test_wiring.py`` grants. Without this the tool would "fix" a
    perfectly correct ``SessionStart`` matcher from ``.*`` to ``*``, an out-of-scope rewrite of
    wiring nobody asked it to touch. Any other declared matcher must match exactly, because for
    those the gate itself asserts string equality.
    """

    if expected == "*":
        return actual in {"*", ".*"}
    return actual == expected


def _groups(settings: dict, event: str) -> list:
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        raise WiringError("settings.json has no 'hooks' object")
    groups = hooks.get(event)
    return groups if isinstance(groups, list) else []


def _group_commands(group: object) -> list[str]:
    if not isinstance(group, dict):
        return []
    return [
        str(h.get("command") or "")
        for h in (group.get("hooks") or [])
        if isinstance(h, dict)
    ]


def plan(settings: dict, manifest: dict, claude_root: Path) -> list[dict]:
    """Compute the ordered change list.  Pure: never mutates ``settings``."""

    events = manifest.get("events")
    if not isinstance(events, dict) or not events:
        raise WiringError("manifest declares no events")

    dispatch_abs = claude_root / "hooks" / DISPATCH_RELPATH
    changes: list[dict] = []
    dispatched_events = 0

    for event, decl in events.items():
        if not isinstance(decl, dict):
            continue
        groups = _groups(settings, event)
        hits = [
            i
            for i, g in enumerate(groups)
            if any(
                references(c, DISPATCH_RELPATH) or _norm(str(dispatch_abs)) in _norm(c)
                for c in _group_commands(g)
            )
        ]
        expected = decl.get("settings_matcher")
        if expected is None:
            continue
        dispatched_events += 1
        if len(hits) != 1:
            raise WiringError(
                f"hooks.{event} must carry exactly one local _dispatch group; found {len(hits)}"
            )
        idx = hits[0]
        actual = groups[idx].get("matcher")
        if not matcher_satisfies(actual, expected):
            changes.append(
                {
                    "kind": "set-matcher",
                    "event": event,
                    "index": idx,
                    "from": actual,
                    "to": expected,
                }
            )

        declared = {
            _norm(str(c.get("script") or ""))
            for c in (decl.get("checks") or [])
            if isinstance(c, dict)
        }
        for legacy, successor in (SUPERSEDED_STANDALONE.get(event) or {}).items():
            for i, group in enumerate(groups):
                cmds = _group_commands(group)
                if not cmds or not all(references(c, legacy) for c in cmds):
                    continue
                if _norm(successor) not in declared:
                    raise WiringError(
                        f"refusing to drop the standalone {legacy!r} group in hooks.{event}: "
                        f"its successor {successor!r} is not a declared manifest check"
                    )
                changes.append(
                    {
                        "kind": "drop-superseded",
                        "event": event,
                        "index": i,
                        "legacy": legacy,
                        "successor": successor,
                    }
                )

    if dispatched_events == 0:
        raise WiringError(
            "no event declares a settings_matcher; refusing to act on a blind scan"
        )
    return changes


def apply_changes(settings: dict, changes: list[dict]) -> dict:
    """Return a NEW settings dict with ``changes`` applied.  Drops run last, high index first."""

    out = json.loads(json.dumps(settings))
    for change in changes:
        if change["kind"] == "set-matcher":
            out["hooks"][change["event"]][change["index"]]["matcher"] = change["to"]
    drops = sorted(
        (c for c in changes if c["kind"] == "drop-superseded"),
        key=lambda c: (c["event"], -c["index"]),
    )
    for change in drops:
        del out["hooks"][change["event"]][change["index"]]
    return out


def verify(settings: dict, manifest: dict, claude_root: Path) -> list[str]:
    """Post-conditions.  Returns problems; empty means the wiring is correct."""

    problems: list[str] = []
    for event, decl in (manifest.get("events") or {}).items():
        if not isinstance(decl, dict) or decl.get("settings_matcher") is None:
            continue
        expected = decl["settings_matcher"]
        groups = _groups(settings, event)
        hits = [
            g
            for g in groups
            if any(references(c, DISPATCH_RELPATH) for c in _group_commands(g))
        ]
        if len(hits) != 1:
            problems.append(f"hooks.{event}: {len(hits)} dispatcher groups, expected 1")
            continue
        if not matcher_satisfies(hits[0].get("matcher"), expected):
            problems.append(f"hooks.{event}: matcher does not mirror the manifest")
        for legacy in SUPERSEDED_STANDALONE.get(event) or {}:
            if any(
                all(references(c, legacy) for c in _group_commands(g))
                and _group_commands(g)
                for g in groups
            ):
                problems.append(
                    f"hooks.{event}: superseded {legacy} is still wired standalone"
                )
    return problems


def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + ".deploy-tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def _render(settings: dict) -> str:
    return json.dumps(settings, indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--claude-root",
        default=str(Path(os.path.expanduser("~")) / ".claude"),
        help="root holding settings.json and hooks/_dispatch/manifest.json",
    )
    ap.add_argument(
        "--apply", action="store_true", help="write the change (default: dry run)"
    )
    ap.add_argument(
        "--no-backup", action="store_true", help="skip the timestamped backup"
    )
    args = ap.parse_args(argv)

    root = Path(args.claude_root)
    settings_path = root / "settings.json"
    manifest_path = root / "hooks" / "_dispatch" / "manifest.json"

    try:
        settings = _load_json(settings_path)
        manifest = _load_json(manifest_path)
        changes = plan(settings, manifest, root)
    except WiringError as exc:
        print(f"FAILED:deploy-dispatch-wiring {exc}")
        return 1

    for change in changes:
        if change["kind"] == "set-matcher":
            print(f"  set-matcher hooks.{change['event']}[{change['index']}]")
            print(f"      from: {change['from']!r}")
            print(f"        to: {change['to']!r}")
        else:
            print(
                f"  drop-superseded hooks.{change['event']}[{change['index']}] "
                f"{change['legacy']} (superseded by {change['successor']})"
            )

    if not changes:
        problems = verify(settings, manifest, root)
        if problems:
            print(
                "FAILED:deploy-dispatch-wiring no plan yet post-conditions fail: "
                + "; ".join(problems)
            )
            return 1
        print("SUCCESS:deploy-dispatch-wiring already in sync (0 changes)")
        return 0

    if not args.apply:
        print(
            f"SUCCESS:deploy-dispatch-wiring dry-run {len(changes)} change(s); re-run with --apply"
        )
        return 0

    updated = apply_changes(settings, changes)
    problems = verify(updated, manifest, root)
    if problems:
        print(
            "FAILED:deploy-dispatch-wiring post-conditions fail, nothing written: "
            + "; ".join(problems)
        )
        return 1

    if not args.no_backup:
        stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = settings_path.with_name(f"settings.json.bak-wiring-{stamp}")
        backup.write_bytes(settings_path.read_bytes())
        print(f"  backup: {backup}")

    _atomic_write(settings_path, _render(updated))

    reread = _load_json(settings_path)
    problems = verify(reread, manifest, root)
    if problems:
        print(
            "FAILED:deploy-dispatch-wiring written file fails post-conditions: "
            + "; ".join(problems)
        )
        return 1
    print(f"SUCCESS:deploy-dispatch-wiring applied {len(changes)} change(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
