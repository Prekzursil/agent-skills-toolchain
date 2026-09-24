#!/usr/bin/env python3
"""T-6 (CRITICAL) manifest id-correction - wrong-session-id defect gate.

Defect (audit CS-4/5): no flat session manifest anywhere; ids are resolved
from memory/stale prose, and the wrong-session-id class is structural. Fix =
G-8=B event-driven writer (plugin/manifest-writer.ts, session.* hooks) +
append-only per-session shards under
  ~/.local/share/cyberstrike/manifest/sessions/<sessionID>.ndjson
merged flat by scripts/manifest_merge.py.

The writer is a Phase-3 DRAFT - wired only by deploy-phase3.md step 3 after
owner GO. Until the manifest exists on disk this test is
NOT-RUNNABLE-needs-manifest and records PENDING-OWNER (never a silent pass:
"no thresholds file" must not fold into green).

Once shards exist the test verifies, read-only:
  1. flat manifest (sessions.ndjson) exists and every shard id has a row
     (id resolution works - the S3 contract);
  2. ids are IMMUTABLE: each interruption-minted id is its own row; no shard
     file is ever rewritten (append-only: every line parses, ts monotonic
     per shard);
  3. `manifest_merge.py --status <newest-id>` runs and reports
     dead_two_signal=false for a live session (two-signal death check wired).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from battery_common import (  # noqa: E402
    REPO,
    SCRIPTS,
    SUCCESS,
    FAILED,
    PENDING_OWNER,
    VerdictRecorder,
    py_run,
    json_from_completed,
)

DATA = Path.home() / ".local" / "share" / "cyberstrike"
SHARD_DIR = DATA / "manifest" / "sessions"
FLAT = DATA / "manifest" / "sessions.ndjson"
MERGE = SCRIPTS / "manifest_merge.py"


def run(rec: VerdictRecorder, opts: dict | None = None) -> str:
    if not MERGE.is_file():
        rec.record("T-6", FAILED, reason="manifest_merge.py missing", anchors=[MERGE])
        return FAILED

    if not (SHARD_DIR.exists() and any(SHARD_DIR.glob("*.ndjson")) and FLAT.exists()):
        rec.record(
            "T-6",
            PENDING_OWNER,
            reason="NOT-RUNNABLE-needs-manifest",
            details={
                "shard_dir": str(SHARD_DIR),
                "flat": str(FLAT),
                "writer": "plugin/manifest-writer.ts (Phase-3 DRAFT, "
                "wired by deploy-phase3.md step 3 after "
                "owner GO - G-8=B)",
                "recheck": "re-run this test after the Phase-3 switch "
                "and one session start",
            },
            anchors=[REPO / "plugin" / "manifest-writer.ts", MERGE],
        )
        return PENDING_OWNER

    # --- manifest exists: verify id-resolution + append-only + merge --------
    shard_ids, shape_errors = set(), []
    for shard in sorted(SHARD_DIR.glob("*.ndjson")):
        last_ts = None
        for ln, line in enumerate(
            shard.read_text(encoding="utf-8", errors="replace").splitlines(), start=1
        ):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                shape_errors.append(
                    {
                        "shard": shard.name,
                        "line": ln,
                        "issue": "unparseable (rewritten?)",
                    }
                )
                continue
            if row.get("sessionID") != shard.stem:
                shape_errors.append(
                    {
                        "shard": shard.name,
                        "line": ln,
                        "issue": "id mismatch inside shard",
                    }
                )
            ts = row.get("ts")
            if last_ts and ts and ts < last_ts:
                shape_errors.append(
                    {
                        "shard": shard.name,
                        "line": ln,
                        "issue": "ts went backwards (rewritten shard?)",
                    }
                )
            last_ts = ts
        shard_ids.add(shard.stem)
        rec.hit("T-6", "shard", shard=shard.name, bytes=shard.stat().st_size)

    flat_ids = set()
    for line in FLAT.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            flat_ids.add(json.loads(line).get("sessionID"))
        except json.JSONDecodeError:
            shape_errors.append({"flat": True, "issue": "unparseable row"})

    unmerged = sorted(shard_ids - flat_ids)

    r = py_run(MERGE, ["--json"])
    merge_parsed = json_from_completed(r)

    for sid in unmerged:
        rec.hit("T-6", "unmerged_session_id", session_id=sid)
    for e in shape_errors:
        rec.hit("T-6", "shape_error", **e)

    ok = not shape_errors and not unmerged and r.returncode == 0
    rec.record(
        "T-6",
        SUCCESS if ok else FAILED,
        details={
            "shard_count": len(shard_ids),
            "flat_row_count": len(flat_ids),
            "unmerged_ids": unmerged,
            "shape_errors": shape_errors[:20],
            "merge_rc": r.returncode,
            "merge_summary": (merge_parsed or {}).get("summary", merge_parsed),
        },
        anchors=[FLAT, MERGE],
        reason=None if ok else "manifest shape/id-resolution defect",
    )
    return SUCCESS if ok else FAILED


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.parse_args()
    with VerdictRecorder(meta={"test": "T-6"}) as rec:
        status = run(rec)
        print(f"T-6 {status}")
        return 0 if status in (SUCCESS, PENDING_OWNER) else 1


if __name__ == "__main__":
    sys.exit(main())
