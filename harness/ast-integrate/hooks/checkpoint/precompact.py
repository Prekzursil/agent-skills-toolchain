#!/usr/bin/env python3
"""PreCompact hook: write `.beads/context/execution-state.md` before history is compacted.

Register in `~/.claude/settings.json` under `hooks.PreCompact` (see `wire.py --print-patch`).

CONTRACT
  * stdin  : the host's PreCompact JSON (session_id, transcript_path, trigger, cwd).
  * stdout : `{"suppressOutput": true}` -- PreCompact output is not injected as context, and
             cluttering the transcript at the exact moment it is being compacted is pointless.
  * stderr : one typed line `CHECKPOINT-WRITE: <STATE> <detail>` so an operator can see the
             result. Under P2-01 a check that cannot prove it executed emits NOT-CHECKED here,
             never nothing.
  * exit   : ALWAYS 0. A checkpoint hook that can block a compaction is worse than no checkpoint.

COST: bounded. All transcript access goes through `_shared/transcript_tail` (tail-only, measured
0.001-0.028 s on 27-109 MB slices vs 1.98-9.43 s for a forward scan), plus at most three git
calls each capped at 3 s. `--selftest` prints a timing so the budget claim stays falsifiable.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
# NOT `import state`. `_dispatch/dispatch.py` loads checks IN-PROCESS and only purges the two
# names in its `_SHARED_NAMES` tuple (`_common`, `stubscan`) between them, so any other bare
# dir-local module name stays cached in `sys.modules` for every later check in that process.
# A uniquely-named module cannot be handed to, or receive, another hook's sibling.
import checkpoint_state as state  # noqa: E402


def main() -> int:
    started = time.monotonic()
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
        sys.stderr.write("CHECKPOINT-WRITE: NOT-CHECKED disabled-by-.disabled-marker\n")
        print(json.dumps({"suppressOutput": True}))
        return 0

    result = state.write_execution_state(event)
    elapsed = time.monotonic() - started
    sys.stderr.write(
        f"CHECKPOINT-WRITE: {result['state']} {result['reason']} "
        f"seq={result['compaction_seq']} bytes={result['bytes']} "
        f"elapsed={elapsed:.3f}s path={result['path']}\n"
    )
    print(json.dumps({"suppressOutput": True}))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        # Absolute last resort: never let a checkpoint hook take down a compaction.
        try:
            sys.stderr.write("CHECKPOINT-WRITE: NOT-CHECKED unhandled-exception\n")
            print(json.dumps({"suppressOutput": True}))
        except Exception:
            pass
        sys.exit(0)
