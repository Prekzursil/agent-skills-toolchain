#!/usr/bin/env python
"""SubagentStart hook — inject the active goal into every spawned subagent.

WHY: AGENTS.md §5 says "re-anchor the goal at the top of every subagent handoff".
Today that is prose-only; agents may not do it.  This hook makes it a MECHANICAL
GUARANTEE: every subagent, regardless of how it was spawned, receives the verbatim
active goal in its initial context.

HOW: reads the event-ledger the same way goal-reinject/reinject.py does, then
emits hookSpecificOutput.additionalContext with a one-line prefix:
    "[subagent-lifecycle] You are subagent '<type>'; the active goal is: <goal>"

Claude Code prepends this to the subagent's initial prompt.

FAIL-OPEN: any exception → exit 0, no output.  Never blocks (exit 2 unused).
OPT-OUT: create a `.disabled` file next to this script, or set
         SUBAGENT_LIFECYCLE=off in the environment.

Stdin (SubagentStart event JSON):
    session_id : str
    cwd        : str
    agent_type : str   e.g. "coder", "architect", "code-reviewer"
    ...
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Add our directory to sys.path so _common is importable.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import emit_context, get_goal, is_opted_out  # noqa: E402


# ---------------------------------------------------------------------------
# Pure helpers (testable without I/O)
# ---------------------------------------------------------------------------


def build_context(agent_type: str, goal: str) -> str:
    """Return the goal-injection string for the spawned subagent.

    Prefixed with [subagent-lifecycle] so it is identifiable in transcripts.
    """
    return (
        f"[subagent-lifecycle] You are subagent '{agent_type}'; "
        f"the active goal is: {goal}"
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    try:
        if is_opted_out():
            return 0

        try:
            data = json.loads(sys.stdin.read() or "{}")
        except Exception:
            return 0  # malformed stdin — fail-open

        agent_type = str(data.get("agent_type") or "unknown")
        cwd = str(data.get("cwd") or os.getcwd())

        goal = get_goal(cwd)
        if goal:
            emit_context("SubagentStart", build_context(agent_type, goal))

    except Exception:
        pass  # fail-open: any unexpected error → silent exit 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
