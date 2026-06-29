#!/usr/bin/env python3
r"""bg-registry/reconcile.py — SessionStart orphan reconciler (READER-only).

THE keystone payoff: on every SessionStart, scan the registry for background / sub-agent
work that was left "running" by a PRIOR session (the session that got restarted/killed),
and LOUDLY surface anything that looks dead so it is resumed or discarded instead of
silently lost.

A record is ORPHANED when ALL hold:
  * status is still "running" (done_marker never closed it),
  * it belongs to a DIFFERENT session than the current one (the current session's
    in-flight work is not orphaned),
  * it is older than a small grace window (avoids racing a just-launched parallel job),
  * its declared artifact does NOT exist / is incomplete (no completed output), AND
  * its pid (if any) is NOT alive in the OS process table (the process really is gone).

READER-only: this NEVER restarts work and NEVER mutates the registry. It only reads the
NDJSON + does cheap OS checks (OpenProcess, os.stat) and records surfaced ids in a
SEPARATE sidecar (.reconciled.json) so each orphan alerts exactly ONCE (no nagging).

FAIL-OPEN: any error -> exit 0, silent. Opt-out: BG_REGISTRY=off or a .disabled file.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS))
import _common as C  # noqa: E402

DISABLED = THIS / ".disabled"
# Grace window: ignore records younger than this (seconds) so a sibling session's
# brand-new job is never flagged before it has had any chance to run.
GRACE = int(os.environ.get("BG_REGISTRY_MIN_AGE_SEC", "120"))


def _disabled() -> bool:
    return DISABLED.exists() or os.environ.get("BG_REGISTRY", "").lower() in ("off", "0", "false")


def find_orphans(current_sid: str, seen: dict) -> list:
    orphans = []
    if not C.BG_DIR.exists():
        return orphans
    for f in sorted(C.BG_DIR.glob("*.ndjson")):
        eff = C.fold(C.read_records(f))
        for rid, rec in eff.items():
            if rec.get("status") != "running":
                continue
            if rec.get("session") == current_sid:
                continue  # current session's in-flight work — not an orphan
            if rid in seen:
                continue  # already surfaced once
            started = 0.0
            try:
                started = float(rec.get("started_ts") or 0)
            except (TypeError, ValueError):
                started = 0.0
            if started and (C.now() - started) < GRACE:
                continue  # too fresh to judge
            if C.artifact_complete(rec.get("expected_artifact")):
                continue  # produced its output -> completed, not orphaned
            pid = rec.get("pid")
            if pid and C.pid_alive(pid) is True:
                continue  # process still running -> not orphaned
            orphans.append(rec)
    return orphans


def format_alert(orphans: list) -> str:
    items = []
    for o in orphans:
        rid = o.get("id")
        kind = o.get("kind") or "?"
        since = C.fmt_ts(o.get("started_ts"))
        art = o.get("expected_artifact")
        what = (f"artifact {art} missing/incomplete" if art else "no artifact was produced")
        items.append(f"{rid} ({kind}) appears dead since {since}, {what}")
    return ("[bg-registry] ORPHANED BACKGROUND WORK: " + "; ".join(items)
            + " - resume or discard?")


def main() -> int:
    try:
        if _disabled():
            return 0
        data = C.read_stdin()
        cur = C.session_id(data)
        seen = C.load_seen()
        orphans = find_orphans(cur, seen)
        if not orphans:
            return 0
        ts = C.now()
        for o in orphans:
            seen[str(o.get("id"))] = ts
        C.save_seen(seen)
        C.emit("SessionStart", format_alert(orphans))
    except Exception:
        pass  # fail-open
    return 0


if __name__ == "__main__":
    sys.exit(main())
