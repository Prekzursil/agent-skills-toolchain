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
        out = subprocess.run(
            ["git", "-C", cwd, *args], capture_output=True, text=True, timeout=5
        )
        if out.returncode == 0:
            return out.stdout.strip()
    except Exception:
        pass
    return None


def _beads_knowledge_dir(cwd: str):
    """Find the .beads/knowledge store (project-relative, else home). None if absent."""
    for base in (Path(cwd), Path.home()):
        d = base / ".beads" / "knowledge"
        if d.exists():
            return d
    return None


def _capture_milestones(cwd: str) -> None:
    """F4 success-gated capture: mirror NEW event-ledger milestones into
    .beads/knowledge/decisions.jsonl. A milestone is an EXTERNAL achievement signal that
    works for RE / research / no-CI work (not just a test/build exit) — per the design
    review's E1 fix. Idempotent via a per-project captured-seq marker. Fail-open.
    """
    kdir = _beads_knowledge_dir(cwd)
    if kdir is None:
        return
    milestones = [
        e
        for e in ledger.replay(cwd, 80)
        if e.get("kind") == "milestone" and e.get("text")
    ]
    if not milestones:
        return
    cap_file = ledger._dir(cwd) / "captured.json"
    try:
        last = int(json.loads(cap_file.read_text(encoding="utf-8")).get("seq", 0))
    except Exception:
        last = 0
    new = [m for m in milestones if int(m.get("seq", 0)) > last]
    if not new:
        return
    with (kdir / "decisions.jsonl").open("a", encoding="utf-8") as fh:
        for m in new:
            fh.write(
                json.dumps(
                    {
                        "type": "milestone-capture",
                        "ts": m.get("ts"),
                        "decision": m.get("text"),
                        "alternativesRejected": m.get("alternatives")
                        or m.get("supersedes_failures"),
                        "confidence": "high",  # success-gated: a milestone is an external achievement signal
                        "source": "stop-hook/event-ledger",
                        "ledger_seq": m.get("seq"),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    cap_file.write_text(
        json.dumps({"seq": max(int(m.get("seq", 0)) for m in new)}), encoding="utf-8"
    )


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
    dirty = (
        len([ln for ln in (porcelain or "").splitlines() if ln.strip()])
        if porcelain is not None
        else None
    )
    try:
        ledger.append(
            cwd,
            "turn",
            cwd=cwd,
            head=head,
            branch=branch,
            dirty_files=dirty,
            session=str(data.get("session_id", ""))[:12],
        )
    except Exception:
        # a ledger failure must never break the session
        pass
    # F4 capture: promote new success-gated milestones into the durable knowledge base
    try:
        _capture_milestones(cwd)
    except Exception:
        pass  # fail-open
    return 0


if __name__ == "__main__":
    sys.exit(main())
