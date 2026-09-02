#!/usr/bin/env python3
"""Worker-facing git wrapper for TST-0345.

Real git is /usr/bin/git (or $TST0345_REAL_GIT). Staging, commit, and other
index/history writes are refused so a confused worker cannot sweep a sibling's
paths via `git add -A` on a shared index.

Read-only verbs (status, diff, log, rev-parse, ...) are delegated.
"""
from __future__ import annotations

import os
import subprocess
import sys

REAL_GIT = os.environ.get("TST0345_REAL_GIT") or "/usr/bin/git"

# Verbs that mutate the index, HEAD, refs, or worktree in ways that can
# contaminate a sibling sharing a git dir / index.
WRITE_VERBS = frozenset(
    {
        "add",
        "commit",
        "commit-tree",
        "update-index",
        "write-tree",
        "stash",
        "rebase",
        "reset",
        "merge",
        "cherry-pick",
        "revert",
        "push",
        "clean",
        "restore",
        "rm",
        "mv",
        "checkout",
        "switch",
        "worktree",
        "am",
        "apply",
        "gc",
        "filter-branch",
        "replace",
        "tag",
        "branch",
        "notes",
        "config",
        "update-ref",
        "symbolic-ref",
        "read-tree",
    }
)

# git global options that consume a following argument (see git(1)).
TAKES_VALUE = frozenset(
    {
        "-C",
        "-c",
        "--exec-path",
        "--git-dir",
        "--work-tree",
        "--namespace",
        "--super-prefix",
        "--config-env",
        "--list-cmds",
        "-c",
    }
)


def parse_verb(argv: list[str]) -> str | None:
    """Return the git subcommand, skipping global options."""
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--":
            if i + 1 < len(argv):
                return argv[i + 1]
            return None
        if a in TAKES_VALUE:
            i += 2
            continue
        if a.startswith("--") and "=" in a:
            i += 1
            continue
        if a.startswith("-") and a not in ("-", "--"):
            i += 1
            continue
        return a
    return None


def is_write_command(argv: list[str]) -> tuple[bool, str | None]:
    verb = parse_verb(argv)
    if verb is None:
        return False, None
    return verb in WRITE_VERBS, verb


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    write, verb = is_write_command(args)
    if write:
        worker = os.environ.get("TST0345_WORKER_ID") or "unknown"
        sys.stderr.write(
            f"TST-0345: git write refused: {verb} "
            f"(worker={worker} staging/commit is not permitted)\n"
        )
        return 2
    real = REAL_GIT
    try:
        return subprocess.call([real, *args])
    except OSError as exc:
        sys.stderr.write(f"TST-0345: real git {real!r} failed: {exc}\n")
        return 127


if __name__ == "__main__":
    raise SystemExit(main())
