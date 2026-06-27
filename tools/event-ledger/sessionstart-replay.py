#!/usr/bin/env python
"""SessionStart hook → inject the ground-truth ledger tail (anti-echo-chamber recovery).

On resume/compact/clear we REPLAY the append-only ledger rather than trusting a lossy
self-summary: recent objective turns + open FAILURES (so dead-ends aren't re-walked) +
the recorded goal. We also diff the recorded HEAD against the live HEAD and surface drift,
so a stale reload can't be silently mistaken for current state. Record-only; exit 0.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ledger  # noqa: E402

MAX_TURNS = 12


def _live_head(cwd: str) -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return out.stdout.strip() if out.returncode == 0 else None
    except Exception:
        return None


def build_context(cwd: str) -> str | None:
    events = ledger.replay(cwd, n=60)
    if not events:
        return None
    st = ledger.state(cwd)
    lines = ["## Event ledger (ground truth — replayed, not summarized)"]
    if st.get("goal"):
        lines.append(f"**Goal:** {st['goal']}")
    open_fail = st.get("open_failures") or []
    if open_fail:
        lines.append(
            "**Open failures (hypotheses — re-test cheaply before trusting):**"
        )
        for f in open_fail[-8:]:
            pc = f" [if: {f['preconditions']}]" if f.get("preconditions") else ""
            lines.append(f"- (#{f.get('seq')}) {f.get('text')}{pc}")
    # HEAD drift check
    rec_head = st.get("head")
    live = _live_head(cwd)
    if rec_head and live and rec_head != live:
        lines.append(
            f"⚠️ **HEAD drift:** ledger last saw `{rec_head}`, live is `{live}` — "
            f"verify what changed before acting on the tail below."
        )
    # recent decisions/failures/milestones + a few turns
    notable = [
        e
        for e in events
        if e.get("kind") in ("decision", "failure", "goal", "milestone")
    ][-10:]
    if notable:
        lines.append("**Recent decisions/notes:**")
        for e in notable:
            lines.append(f"- [{e.get('kind')}] {e.get('text', '')}")
    turns = [e for e in events if e.get("kind") == "turn"][-MAX_TURNS:]
    if turns:
        first, last = turns[0], turns[-1]
        lines.append(
            f"**Turn timeline:** {len(turns)} recent turns, "
            f"HEAD {first.get('head')}→{last.get('head')} on `{last.get('branch')}` "
            f"(dirty: {last.get('dirty_files')} files)."
        )
    return "\n".join(lines)


def main() -> int:
    try:
        data = json.loads(sys.stdin.read() or "{}")
    except Exception:
        data = {}
    cwd = data.get("cwd") or "."
    # Only inject on recovery paths (resume/compact/clear) — not on every fresh startup,
    # to keep token cost off the normal-start path. /clear is included because PreCompact
    # does NOT fire on it (#13572), so this is the only ledger-recovery for that path.
    if data.get("source") not in ("resume", "compact", "clear"):
        return 0
    try:
        ctx = build_context(cwd)
    except Exception:
        ctx = None
    if ctx:
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "SessionStart",
                        "additionalContext": ctx,
                    }
                }
            )
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
