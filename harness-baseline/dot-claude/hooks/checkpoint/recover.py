#!/usr/bin/env python3
"""SessionStart hook: reconstruct execution state from disk after a compaction/resume/clear.

Register in `~/.claude/settings.json` under `hooks.SessionStart`, or as a `_dispatch` check
(see `wire.py --print-patch`).

CONTRACT
  * stdin  : the host's SessionStart JSON (session_id, cwd, source).
  * stdout : `{"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": …}}`
             for every state EXCEPT CLEAN.
  * stderr : `CHECKPOINT-RECOVER: <STATE> …` for EVERY state including CLEAN, so the typed
             verdict always surfaces to an operator even when the transcript stays quiet.
  * exit   : ALWAYS 0.

WHY CLEAN IS THE ONLY SILENT STATE
  CLEAN means: a fresh `startup`, we looked, and there is genuinely nothing to recover. Every
  other state has something the session needs to know -- including FINDING, which fires when a
  recovery-path start finds NO checkpoint. That case is the dead-man switch for the PreCompact
  half: without it, an unwired writer and a session with nothing to recover are indistinguishable,
  which is precisely how 101 checkpoint files came to be written and never read.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
# NOT `import state` -- see the note in precompact.py: `_dispatch/dispatch.py` loads checks
# in-process and purges only `_common`/`stubscan` from sys.modules between them, so a bare
# dir-local name would be visible to (and collide with) every later check in that process.
import checkpoint_state as state  # noqa: E402


def main() -> int:
    try:
        raw = sys.stdin.read()
    except Exception:
        raw = ""
    try:
        event = json.loads(raw or "{}")
    except Exception:
        event = {}
    if not isinstance(event, dict):
        event = {}

    if (Path(__file__).resolve().parent / ".disabled").exists():
        sys.stderr.write(
            "CHECKPOINT-RECOVER: NOT-CHECKED disabled-by-.disabled-marker\n"
        )
        return 0

    verdict, context = state.recover(event)
    sys.stderr.write(
        f"CHECKPOINT-RECOVER: {verdict} source={event.get('source', '?')} "
        f"chars={len(context or '')}\n"
    )
    if verdict == state.CLEAN or not context:
        return 0
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": context,
                }
            }
        )
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        try:
            sys.stderr.write("CHECKPOINT-RECOVER: NOT-CHECKED unhandled-exception\n")
        except Exception:
            pass
        sys.exit(0)
