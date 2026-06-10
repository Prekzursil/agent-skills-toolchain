#!/usr/bin/env python
"""Stop hook → append an objective per-turn event to the ledger.

This is the continuous, hook-written half of the keystone: every time Claude finishes a
turn we record an objective snapshot (git HEAD, branch, dirty-file count, cwd). It is
RECORD-ONLY — it never blocks (always exit 0) and honors stop_hook_active so it can never
cause a loop. The ledger thus stays current *before* compaction, so recovery replays
ground truth rather than a summary written from an already-degraded context.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ledger  # noqa: E402


def _git(cwd: str, *args: str) -> str | None:
    try:
        out = subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True, timeout=5)
        if out.returncode == 0:
            return out.stdout.strip()
    except Exception:
        pass
    return None


def main() -> int:
    try:
        data = json.loads(sys.stdin.read() or "{}")
    except Exception:
        data = {}
    # never loop: if we're already inside a stop-hook continuation, do nothing
    if data.get("stop_hook_active"):
        return 0
    cwd = data.get("cwd") or "."
    head = _git(cwd, "rev-parse", "--short", "HEAD")
    branch = _git(cwd, "rev-parse", "--abbrev-ref", "HEAD")
    porcelain = _git(cwd, "status", "--porcelain")
    dirty = len([l for l in (porcelain or "").splitlines() if l.strip()]) if porcelain is not None else None
    try:
        ledger.append(cwd, "turn", cwd=cwd, head=head, branch=branch, dirty_files=dirty,
                      session=str(data.get("session_id", ""))[:12])
    except Exception:
        # a ledger failure must never break the session
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
