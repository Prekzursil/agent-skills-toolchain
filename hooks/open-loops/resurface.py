#!/usr/bin/env python3
r"""open-loops/resurface.py — SessionStart check (folded into _dispatch/manifest.json).

PROSPECTIVE MEMORY at resume time: surface the 1-3 most-relevant OPEN LOOPS for the
current context so a forgotten thread is re-entered instead of silently dropped:

  * trigger store matches  — "when X happens do Y" intentions whose condition holds in
    THIS context (cwd / git branch / file-exists / recent files), unfired & unexpired;
  * standing loops         — `always` reminders (no context predicate), shown passively;
  * ledger open loops      — unresolved failures + a dangling goal, BUT only on a FRESH
    start. On resume/compact/clear the event-ledger/sessionstart-replay hook already
    replays those verbatim, so we suppress them here to avoid duplication.

This is the SessionStart half (passive list — does NOT mark anything fired). The active
"fire it now" half is trigger_match.py on UserPromptSubmit.

NOT a duplicate of:
  * persist-nudge (Stop: "you did work but saved nothing") — that is a save-prompt;
    this is a resume-time recall of previously-saved intentions.
  * sessionstart-replay (replays ledger turns/failures on recovery) — we defer the
    ledger view to it on recovery and add the user-authored trigger layer it has not.

Dispatcher interface: a `main(argv)` that reads the SessionStart payload on stdin and
prints ONE hookSpecificOutput JSON (or nothing). FAIL-OPEN. Opt-out: OPEN_LOOPS=off or
a .disabled file in this dir.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS))
import _common as C  # noqa: E402

DISABLED = THIS / ".disabled"
MAX_ITEMS = int(os.environ.get("OPEN_LOOPS_MAX_RESURFACE", "3"))
_RECOVERY_SOURCES = ("resume", "compact", "clear")


def _disabled() -> bool:
    return DISABLED.exists() or os.environ.get("OPEN_LOOPS", "").lower() in (
        "off",
        "0",
        "false",
    )


def build_message(payload: dict) -> str | None:
    ctx = C.build_ctx(payload)
    triggers = C.load_triggers(gc=True)
    live = [t for t in triggers if not t.get("fired")]

    contextual, standing = [], []
    for t in live:
        cond = t.get("condition") or {}
        if C.is_contextual(cond):
            if C.eval_condition(cond, ctx):
                contextual.append(t)
        elif C.eval_condition(cond, ctx):  # `always` loop
            standing.append(t)

    # newest first within each bucket
    contextual.sort(key=lambda t: t.get("created_ts", 0), reverse=True)
    standing.sort(key=lambda t: t.get("created_ts", 0), reverse=True)

    lines: list[str] = []
    budget = MAX_ITEMS
    if contextual:
        lines.append("**Triggers matching here (cwd/branch/files):**")
        for t in contextual[:budget]:
            note = C.matched_pred_summary(t.get("condition") or {}, ctx)
            lines.append(f"- ({t['id']}) {t.get('action', '')}  <- {note}")
        budget -= min(budget, len(contextual))
    if standing and budget > 0:
        lines.append("**Standing open loops:**")
        for t in standing[:budget]:
            lines.append(f"- ({t['id']}) {t.get('action', '')}")
        budget -= min(budget, len(standing))

    # Ledger open loops only on a fresh start (replay owns the recovery path).
    if ctx.get("source") not in _RECOVERY_SOURCES:
        for ll in C.ledger_open_loops(ctx.get("cwd", ".")):
            lines.append(f"- (ledger) {ll}")

    if not lines:
        return None
    header = "## Open loops & prospective memory (Zeigarnik — re-enter, don't drop)"
    footer = (
        "Close a loop when done: `python ~/.claude/hooks/open-loops/add.py "
        '--close <id>`  |  add one: `add.py "when <cond> -> <action>"`'
    )
    return "\n".join([header, *lines, footer])


def main(argv=None) -> int:
    try:
        if _disabled():
            return 0
        payload = C.read_stdin()
        msg = build_message(payload)
        if msg:
            C.emit("SessionStart", msg)
    except Exception:
        pass  # fail-open: never crash a session
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
