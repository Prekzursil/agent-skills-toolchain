#!/usr/bin/env python3
"""agentmon — open one live tail terminal per active Claude Code subagent.

The ``mon agentmon`` / ``Task``-trigger entry: discover every active ``subagents/agent-*.jsonl``
(flat or under a workflow) via ``monitorcore.discovery``, then open one Windows-Terminal tab per
agent live-tailing it via ``monitorcore.spawn`` (the wt → PowerShell → bare-Python ladder). This
is the agent-domain counterpart to the ``workflow-monitor`` whole-fleet cockpit. Read-only — it
only reads each subagent's own transcript.

``monitorcore`` is vendored inside the SIBLING ``workflow-monitor`` skill, so that dir is put on
``sys.path`` (mirrors ``tail_once.py``); this resolves both in-repo (``skills/workflow-monitor``)
and deployed (``~/.agents/skills/workflow-monitor``).

With no argument the newest-activity session wins (``discovery.pick_active_dir``), and with TWO
live sessions that global-newest pick can flip between runs (MON-agentmon-1) — so the chosen dir
is always printed, and ``--list`` / ``--session`` / ``--dir`` let an operator see the candidate
sessions and pin the one to tail. ``mon agentmon`` forwards extra args to this script.

Usage:  python agentmon.py                     (newest-activity session, tail each active agent)
        python agentmon.py --list              (list live subagent dirs, newest first, and exit)
        python agentmon.py --session <substr>  (pin by substring of the <project>/<session> path)
        python agentmon.py --dir <path>        (pin an explicit subagents dir, or its parent)
"""

from __future__ import annotations

import argparse
import os
import sys
import time

# The sibling workflow-monitor skill vendors ``monitorcore`` — put it on sys.path.
_SKILLS_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_WFMON = os.path.join(_SKILLS_ROOT, "workflow-monitor")
if _WFMON not in sys.path:
    sys.path.insert(0, _WFMON)

from monitorcore import discovery, spawn  # noqa: E402  (intentional: after sys.path setup)

# A subagent transcript counts as active if its .jsonl advanced within this window.
_ACTIVE_SECS = 150.0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        prog="agentmon",
        description="Open one live tail terminal per active Claude Code subagent.",
    )
    g = ap.add_mutually_exclusive_group()
    g.add_argument(
        "--list",
        action="store_true",
        help="list live subagent dirs (newest first, * = default pick) and exit",
    )
    g.add_argument(
        "--session",
        metavar="SUBSTR",
        help="tail the session whose <project>/<session> path contains SUBSTR "
        "(newest match wins)",
    )
    g.add_argument(
        "--dir",
        dest="dir_",
        metavar="PATH",
        help="tail an explicit subagents dir (PATH itself, or PATH/subagents)",
    )
    return ap.parse_args(argv)


def _ranked_dirs() -> list[tuple[float, str]]:
    """Every subagents dir holding transcripts as ``(newest mtime, dir)``, newest first."""
    pairs = [(discovery.newest_mtime(d), d) for d in discovery.find_subagent_dirs()]
    # Path is the tiebreak so equal-mtime dirs list in a stable order.
    pairs.sort(key=lambda p: (-p[0], p[1]))
    return pairs


def _list_dirs() -> int:
    pairs = _ranked_dirs()
    if not pairs:
        print("agentmon: no subagent directory found")
        return 1
    now = time.time()
    for i, (mtime, d) in enumerate(pairs):
        mark = "*" if i == 0 else " "
        print(f"{mark} {d}  (last activity {max(0.0, now - mtime):.0f}s ago)")
    print("agentmon: * = default pick; pin another with --session/--dir")
    return 0


def _pick_subdir(args: argparse.Namespace) -> str | None:
    """The subagents dir to tail, or ``None`` (after printing why) when nothing matches."""
    if args.dir_:
        nested = os.path.join(args.dir_, "subagents")
        subdir = nested if os.path.isdir(nested) else args.dir_
        if not os.path.isdir(subdir):
            print(f"agentmon: --dir not found: {args.dir_}")
            return None
        return subdir
    if args.session:
        # normcase both sides: Windows paths compare case-insensitively, and it also maps
        # a forward-slash needle like projA/sessA onto the backslash form the walk yields.
        needle = os.path.normcase(args.session)
        matches = [(m, d) for m, d in _ranked_dirs() if needle in os.path.normcase(d)]
        if not matches:
            print(
                f"agentmon: no subagent directory matches --session {args.session!r}"
                " (see --list)"
            )
            return None
        return matches[0][1]  # ranked newest-first, so the newest match wins
    subdir = discovery.pick_active_dir()
    if not subdir:
        print("agentmon: no active subagent directory found")
    return subdir


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.list:
        return _list_dirs()
    subdir = _pick_subdir(args)
    if not subdir:
        return 1
    print(f"agentmon: tailing {subdir}")
    rows = discovery.scan(subdir, _ACTIVE_SECS, 120)
    active = [r for r in rows if r["running"]]
    if not active:
        print(f"agentmon: no active subagents under {subdir}")
        return 0
    n = spawn.spawn(active, use_wt=True, tabs=True)
    print(f"agentmon: opened {n} agent tail window(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
