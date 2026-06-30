#!/usr/bin/env python3
r"""ulysses/enforce.py — PreToolUse hook (its OWN settings.json entry).

Evaluates the self-authored tripwires (ulysses/tripwires.json) against every matched
tool call. This is the ENFORCEMENT half of the Ulysses contract:

  * HARD trip (HALT)      -> exit 2 (BLOCK) with the reason on stderr. The genuinely
                             dangerous, irreversible case (e.g. forcing an unverified
                             field into LIVE game memory) — the only thing AGENTS.md §6
                             permits a block for. Also blocks a silent disarm of the
                             tripwires file itself (no logged override).
  * SOFT trip (ASK)       -> inject "you committed to ask before X" (exit 0).
  * SOFT trip (SNAPSHOT)  -> inject "checkpoint before X" (exit 0).
  * no trip / no store    -> silent (exit 0).

NOT a duplicate of:
  * goal-reinject (re-anchors the GOAL every N edits; inject-only, never blocks) — this
    enforces ABORT criteria and can block;
  * edit-checkpoints (snapshots before a write for /rollback) — this evaluates whether a
    write should happen at all.

FAIL-OPEN: any error -> exit 0 (never block by accident). Pure stdlib.
Opt-out: ULYSSES=off or a .disabled file in this dir.

Wire spec:
  Event:   PreToolUse
  Matcher: Edit|Write|MultiEdit|Bash|PowerShell|mcp__cheatengine__.*|mcp__frida-mcp__.*
  Command: python C:/Users/Prekzursil/.claude/hooks/ulysses/enforce.py
  Exit:    0 (allow / inject) | 2 (block; reason on stderr)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS))
import _common as C  # noqa: E402

DISABLED = THIS / ".disabled"


def _disabled() -> bool:
    return DISABLED.exists() or os.environ.get("ULYSSES", "").lower() in (
        "off",
        "0",
        "false",
    )


def main() -> int:
    try:
        if _disabled():
            return 0
        payload = C.read_stdin()
        store = C.load_tripwires()
        if not store:
            return 0  # no armed tripwires (or expired/garbage) -> silent
        ctx = C.build_ctx(payload, store)
        verdict = C.decide(store, ctx)
        v = verdict.get("verdict")
        if v == "halt":
            # exit 2 + stderr = block (reason fed back to the model).
            sys.stderr.write(verdict.get("message") or "ULYSSES: blocked by tripwire.")
            sys.stderr.flush()
            return 2
        if v in ("ask", "snapshot"):
            C.emit("PreToolUse", verdict.get("message") or "")
            return 0
    except Exception:
        pass  # fail-open: never block on an internal error
    return 0


if __name__ == "__main__":
    sys.exit(main())
