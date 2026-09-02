#!/usr/bin/env python3
"""Fixture PreToolUse hook: exit 2 only for irreversible git/publish/cloud danger.

This file is a REPOSITORY copy of a would-be guard. It is not registered in the
shipped worktree (no hooks/ dispatcher, no settings.json hook list). Direct
invocation proves the script can refuse; absence of wiring proves it is UNARMED
in the configuration that actually runs.
"""
from __future__ import annotations

import json
import sys

DANGER = (
    "git push --force",
    "git push -f",
    "git reset --hard",
    "git rebase -i",
    "npm publish",
    "twine upload",
    "gh repo create",
    "scw instance server create",
)


def dangerous(command: str) -> bool:
    folded = " ".join(command.lower().split())
    return any(token in folded for token in DANGER)


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        # Fail-open on internal error (hook contract: non-danger must not exit 2).
        return 0
    tool = str(payload.get("tool_name") or payload.get("tool") or "")
    cmd = str(
        payload.get("command")
        or (payload.get("tool_input") or {}).get("command")
        or ""
    )
    if tool in {"Bash", "Shell", ""} and dangerous(cmd):
        sys.stderr.write("BLD-0052 fixture hook: irreversible danger\n")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
