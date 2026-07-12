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

Usage:  python agentmon.py            (discover the active session's subagents, tail each)
"""

from __future__ import annotations

import os
import sys

# The sibling workflow-monitor skill vendors ``monitorcore`` — put it on sys.path.
_SKILLS_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_WFMON = os.path.join(_SKILLS_ROOT, "workflow-monitor")
if _WFMON not in sys.path:
    sys.path.insert(0, _WFMON)

from monitorcore import discovery, spawn  # noqa: E402  (intentional: after sys.path setup)

# A subagent transcript counts as active if its .jsonl advanced within this window.
_ACTIVE_SECS = 150.0


def main() -> int:
    subdir = discovery.pick_active_dir()
    if not subdir:
        print("agentmon: no active subagent directory found")
        return 1
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
