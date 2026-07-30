#!/usr/bin/env python
"""cmd-rewrite/inject-nopager.py — PreToolUse hook: inject `git --no-pager` into pager-prone git subcommands.

WHY
===
On Windows / Git-Bash, several git subcommands (log, diff, show, branch, tag,
stash list, shortlog, blame, reflog) open a pager (less / more) by default.
When Claude Code's Bash tool runs these, the pager hangs waiting for terminal
input that never arrives, blocking the agent indefinitely.

This hook rewrites the command at the tool boundary by inserting `--no-pager`
immediately after `git`.  For example:

    git log --oneline -5
    →  git --no-pager log --oneline -5

    git diff HEAD~1
    →  git --no-pager diff HEAD~1

SEMANTICS-PRESERVING GUARANTEE
================================
`git --no-pager <subcmd>` is 100% equivalent to `GIT_PAGER=cat git <subcmd>`
in its output content.  This hook NEVER adds --porcelain, --quiet, or any
flag that changes output format.

ONLY-ONE-REWRITER CAVEAT
=========================
Claude Code runs all matching PreToolUse hooks in parallel and the last
`updatedInput` writer wins (non-deterministically if ordering is undefined).
Therefore: DO NOT register a second PreToolUse updatedInput hook that also
targets the Bash tool.  This hook must be the sole rewriter for Bash.
See settings.json registration block in the companion README.md.

FAIL-OPEN CONTRACT
==================
Any error — malformed JSON, unexpected data shape, crash — produces NO output
and exits 0.  The original command passes through unchanged.  This hook can
never block or corrupt a tool call.

Stdin (PreToolUse JSON):
    session_id   str
    tool_name    str        — always "Bash" (enforced by matcher)
    tool_input   dict       — {"command": "<shell command string>"}
    cwd          str

Stdout (on rewrite):
    JSON: {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                   "permissionDecision": "allow",
                                   "updatedInput": {"command": "<rewritten>"}}}

Stdout (no change): nothing — exit 0.
"""

from __future__ import annotations

import json
import re
import sys

# ── Configuration ─────────────────────────────────────────────────────────────

# Subcommands that can invoke a pager.  Only rewrite these.
# `git log` — yes.  `git commit` — no.
PAGER_PRONE: frozenset[str] = frozenset(
    {
        "log",
        "diff",
        "show",
        "branch",
        "tag",
        "stash",  # `git stash list` pages; we rewrite the whole `git stash ...` family
        "shortlog",
        "blame",
        "reflog",
        "diff-tree",
        "diff-index",
        "diff-files",
        "format-patch",
        "whatchanged",
    }
)

# Tokens that split a shell command into logical segments we analyse independently.
# We treat && and ; as segment boundaries.  Pipe (|) is NOT a boundary because
# `git log | head` is fine — the pipe removes the pager need — but we still
# rewrite it to be safe (it's harmless and catches `git log | less` abuses too).
# Actually: piped commands are safe already, but --no-pager is still harmless.
# We parse on &&/; only, leaving pipes inside segments.
_SEG_SPLIT_RE = re.compile(r"(&&|;)")


def _needs_nopager(segment: str) -> bool:
    """Return True if this shell segment is a git invocation that both:
    1. calls a pager-prone subcommand, and
    2. does NOT already carry `--no-pager`.
    """
    stripped = segment.strip()
    # Must start with `git` (possibly with leading env vars like GIT_DIR=...)
    # We only rewrite the simple `git <subcmd>` pattern.  If there are leading
    # env-var assignments (VAR=x git ...) we detect them and still handle them.
    m = re.match(
        r"^(?:[A-Z_][A-Z_0-9]*=[^\s]*\s+)*git(?:\s|$)(.*)",
        stripped,
        re.DOTALL,
    )
    if not m:
        return False
    rest = m.group(1).strip()
    # Already has --no-pager?
    if re.search(r"--no-pager\b", rest):
        return False
    # Extract the subcommand (first non-flag word)
    tokens = rest.split()
    if not tokens:
        return False
    # Skip global flags like --git-dir=, --work-tree=, -C, --no-pager, etc.
    subcommand = None
    for tok in tokens:
        if not tok.startswith("-"):
            subcommand = tok
            break
    if subcommand is None:
        return False
    return subcommand in PAGER_PRONE


def _inject_nopager(segment: str) -> str:
    """Insert --no-pager into `segment`, preserving leading env-var prefixes."""
    stripped = segment.strip()
    leading_space = segment[: len(segment) - len(segment.lstrip())]
    trailing_space = segment[len(segment.rstrip()) :]
    # Find `git` keyword position; insert --no-pager right after it
    m = re.match(
        r"^((?:[A-Z_][A-Z_0-9]*=[^\s]*\s+)*git)(\s+.*|$)",
        stripped,
        re.DOTALL,
    )
    if not m:
        return segment  # should not happen; fail-open
    prefix = m.group(1)  # e.g. "git" or "GIT_DIR=.git git"
    suffix = m.group(2)  # e.g. " log --oneline -5"
    return leading_space + prefix + " --no-pager" + suffix + trailing_space


def _rewrite_command(command: str) -> str | None:
    """Rewrite *command* to inject --no-pager where needed.

    Returns the rewritten string, or None if no change was made.

    Strategy: split on && and ; (preserving the separators), process each
    segment independently.  If ANY segment is risky to parse (e.g. contains
    subshell $(...) or backtick expansions), skip that segment and leave it
    unchanged (fail-open).
    """
    # Guard: if the command contains subshell expansions, we bail out entirely
    # rather than risk mangling it.
    if "$(" in command or "`" in command:
        return None

    parts = _SEG_SPLIT_RE.split(command)
    # parts alternates between segments and separators: [seg, sep, seg, sep, ...]
    changed = False
    result_parts: list[str] = []
    for part in parts:
        if part in ("&&", ";"):
            result_parts.append(part)
        else:
            try:
                if _needs_nopager(part):
                    result_parts.append(_inject_nopager(part))
                    changed = True
                else:
                    result_parts.append(part)
            except Exception:
                # Parsing this segment failed; leave it untouched (fail-open)
                result_parts.append(part)

    if not changed:
        return None
    return "".join(result_parts)


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> int:
    try:
        raw = sys.stdin.read() or "{}"
        data = json.loads(raw)
    except Exception:
        return 0  # fail-open: malformed JSON → passthrough

    try:
        tool_name = data.get("tool_name", "")
        if tool_name != "Bash":
            return 0

        tool_input = data.get("tool_input") or {}
        command = tool_input.get("command")
        if not isinstance(command, str) or not command.strip():
            return 0

        rewritten = _rewrite_command(command)
        if rewritten is None:
            return 0  # no change needed — silent exit

        # `updatedInput` REPLACES the entire tool_input object -- every field the
        # caller sent that we are not changing must be copied through, or it is
        # dropped. Emitting a bare {"command": ...} silently discarded
        # `description`, `timeout` and `run_in_background`, so a requested
        # background call with a 600000 ms timeout became a foreground call at the
        # default timeout. Copy first, then override only `command`.
        updated_input = dict(tool_input)
        updated_input["command"] = rewritten
        out = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "updatedInput": updated_input,
            }
        }
        sys.stdout.write(json.dumps(out, ensure_ascii=False))
        sys.stdout.flush()

    except Exception:
        pass  # fail-open: any logic error → exit 0, do nothing

    return 0


if __name__ == "__main__":
    sys.exit(main())
