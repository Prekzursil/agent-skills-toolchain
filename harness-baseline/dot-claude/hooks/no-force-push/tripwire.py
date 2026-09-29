#!/usr/bin/env python3
r"""no-force-push/tripwire.py - the HALT predicate for the no-force-push gate.

Pure, side-effect-free predicate so it can be unit-tested in isolation:
    should_halt(payload) -> (halt: bool, reason: str)

Kept separate from hook.py (the exit-2 wiring) on purpose - the decision of
WHETHER to block is the part that must be provable; the wiring is trivial.
"""

from __future__ import annotations

import re

KIND = "command"
FIELD = "tool_input.command"
ACTION = "Tripwire: refusing git push --force. Force-push can destroy remote history; AGENTS.md section 9 requires explicit user approval. If approved, re-run with FORGE_NO_FORCE_PUSH_OFF=1."
_PATTERN = re.compile("git\\s+push\\b[^\\n]*(--force\\b|-f\\b)", re.IGNORECASE)


# Use-vs-mention fix, 24.09.2026. _PATTERN matches the literal text of the
# command, so writing a file whose CONTENT documents the forbidden command --
# a test, a runbook, a policy note -- tripped this gate and blocked the write.
# A heredoc written to a FILE SINK is data and is stripped; a heredoc piped to
# an INTERPRETER is code and is still scanned, so smuggling stays blocked.
_SINK_RE = re.compile(
    r"(?:^|[|;&]\s*)\s*(?:cat|tee)\s*>{1,2}"
    r"|git\s+(?:commit|tag|notes)\b[^\n]*\s-F\b",
    re.IGNORECASE,
)
_HD_OPEN_RE = re.compile(r"<<-?\s*([\'\"]?)(\w+)\1")
_MSG_RE = re.compile(r"(?:-m|--message)\s+(\'[^\']*\'|\"[^\"]*\"|\S+)")


def _executable_text(cmd: str) -> str:
    """Return only the part of a command that will actually execute."""
    if not cmd:
        return ""
    out, pos = [], 0
    for m in _HD_OPEN_RE.finditer(cmd):
        if m.start() < pos:
            continue
        line = cmd[cmd.rfind("\n", 0, m.start()) + 1:m.start()]
        tag = m.group(2)
        end = re.search(r"^%s\s*$" % re.escape(tag), cmd[m.end():], re.M)
        body_end = m.end() + (end.end() if end else len(cmd) - m.end())
        if _SINK_RE.search(line):
            out.append(cmd[pos:m.end()])
            pos = body_end
    out.append(cmd[pos:])
    return _MSG_RE.sub(" ", "".join(out))


def _dig(payload: dict, path):
    if not path:
        return None
    cur = payload
    for part in str(path).split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def _source(payload: dict) -> str:
    if KIND == "prompt":
        return str(payload.get("prompt") or "")
    return _executable_text(str(_dig(payload, FIELD) or ""))


def should_halt(payload: dict):
    """Return (True, reason) iff the dangerous pattern is positively detected."""
    src = _source(payload)
    if not src:
        return (False, "")
    count = len(list(_PATTERN.finditer(src)))
    if count == 0:
        return (False, "")
    return (True, ACTION.replace("{count}", str(count)))
