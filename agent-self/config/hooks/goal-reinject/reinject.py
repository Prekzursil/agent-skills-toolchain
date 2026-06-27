#!/usr/bin/env python
"""goal-reinject/reinject.py — PreToolUse hook: anti-tunnel-vision goal re-injection.

Every N write-ops (N=8, configurable via GOAL_REINJECT_INTERVAL env var) AND only
when a goal has been recorded in the event ledger for this project, this hook injects
an additionalContext message that re-anchors the agent to its stated goal.

Why: "drift" causes 65% of 2025 agent failures (per research synthesis). Verbatim
re-injection of the goal every N turns is the evidence-backed fix (ReflAct +27.7%).
The injection is lightweight (one sentence) and non-blocking (always exit 0).

NEVER blocks (exit 2 is not used here). Fails open: any error → no output → exit 0.
Honors: no secrets, no external calls, stdlib only.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
_LEDGER_DIR = str(Path(__file__).resolve().parent.parent / "event-ledger")
sys.path.insert(0, _LEDGER_DIR)

INTERVAL = int(os.environ.get("GOAL_REINJECT_INTERVAL", "8"))
FALSIFY_INTERVAL = int(
    os.environ.get("GOAL_FALSIFY_INTERVAL", "24")
)  # slower cadence: force anchor-falsification + fresh-context verify
COUNTER_ROOT = Path(
    os.environ.get(
        "GOAL_REINJECT_COUNTER_ROOT", str(Path.home() / ".claude" / "goal-reinject")
    )
)


def _counter_file(session_id: str) -> Path:
    """One JSON file per session: {count: int}."""
    COUNTER_ROOT.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "-_." else "-" for c in session_id)[:48]
    h = hashlib.sha256(session_id.encode("utf-8", "replace")).hexdigest()[:8]
    return COUNTER_ROOT / f"{safe}-{h}.json"


def _read_count(session_id: str) -> int:
    f = _counter_file(session_id)
    if f.exists():
        try:
            return int(json.loads(f.read_text(encoding="utf-8")).get("count", 0))
        except Exception:
            pass
    return 0


def _write_count(session_id: str, count: int) -> None:
    f = _counter_file(session_id)
    try:
        f.write_text(json.dumps({"count": count}), encoding="utf-8")
    except Exception:
        pass


def main() -> int:
    try:
        data = json.loads(sys.stdin.read() or "{}")
    except Exception:
        return 0

    # Only count write-class tools (Edit, Write, Bash). The matcher in settings.json
    # already limits delivery, but we guard here too for defensiveness.
    tool = data.get("tool_name", "")
    if tool not in ("Edit", "Write", "Bash"):
        return 0

    # Derive a stable session identifier from the session_id field (or a fallback).
    session_id = str(data.get("session_id") or data.get("cwd") or "unknown")
    cwd = str(data.get("cwd") or ".")

    # Increment the write-op counter.
    count = _read_count(session_id) + 1
    _write_count(session_id, count)

    need_goal = count % INTERVAL == 0
    need_falsify = count % FALSIFY_INTERVAL == 0
    if not (need_goal or need_falsify):
        return 0

    pieces = []

    if need_goal:
        # Pull the goal from the ledger — fail-open if ledger import fails.
        try:
            import ledger  # noqa: PLC0415 — local import after sys.path insert

            st = ledger.state(cwd)
            goal = (st or {}).get("goal")
            if goal:
                pieces.append(
                    f"ACTIVE GOAL (re-anchor): {goal} "
                    f"— confirm this action serves it; if you've drifted, refocus."
                )
        except Exception:
            pass

    if need_falsify:
        pieces.append(
            "FALSIFY-CHECK (many edits in — guard against a wrong anchor): state your "
            "current load-bearing assumption in one line, and the single cheapest test "
            "that would PROVE IT WRONG. If you've relied on it for many steps with no "
            "INDEPENDENT check, invoke the `fresh-context-verify` skill — re-derive it in "
            "a clean context that cannot inherit your reasoning. Do not just retry."
        )

    if pieces:
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "additionalContext": "\n\n".join(pieces),
                    }
                }
            )
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
