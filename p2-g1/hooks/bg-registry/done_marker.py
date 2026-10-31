#!/usr/bin/env python3
r"""bg-registry/done_marker.py — close out completed registry records.

Runs on Stop (and/or SubagentStop). For THIS session's registry it folds the
append-only NDJSON to effective state and appends a "done" status line for every
still-"running" record that has demonstrably completed:

  * its declared artifact now exists and is non-trivial  -> done (reason: artifact), or
  * it is a synchronous sub-agent (sync=true) and the turn has ended -> done
    (reason: turn-ended; a Task() the orchestrator awaited is finished by Stop).

Async/background records with no artifact yet are LEFT running — reconcile.py decides
their fate next SessionStart via pid-liveness. This is the WRITER side of the registry;
it is SILENT (never injects) and FAIL-OPEN. Opt-out: BG_REGISTRY=off or a .disabled file.

Without this marker, reconcile would later mistake a cleanly-finished synchronous
sub-agent for an orphan — so this is what keeps the orphan alert HIGH-signal.
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
    return DISABLED.exists() or os.environ.get("BG_REGISTRY", "").lower() in (
        "off",
        "0",
        "false",
    )


def compute_done(eff: dict) -> list:
    """Return [{id,status:done,reason,done_ts}, ...] for records that have completed."""
    updates = []
    for rid, rec in eff.items():
        if rec.get("status") != "running":
            continue
        art = rec.get("expected_artifact")
        if art and C.artifact_complete(art):
            updates.append(
                {"id": rid, "status": "done", "reason": "artifact", "done_ts": C.now()}
            )
        elif rec.get("sync"):
            updates.append(
                {
                    "id": rid,
                    "status": "done",
                    "reason": "turn-ended",
                    "done_ts": C.now(),
                }
            )
    return updates


def main() -> int:
    try:
        if _disabled():
            return 0
        data = C.read_stdin()
        if data.get("stop_hook_active"):
            return 0  # don't loop on our own continuation
        sid = C.session_id(data)
        path = C.registry_file(sid)
        if not path.exists():
            return 0
        eff = C.fold(C.read_records(path))
        for upd in compute_done(eff):
            C.append_record(sid, upd)
    except Exception:
        pass  # fail-open
    return 0


if __name__ == "__main__":
    sys.exit(main())
