#!/usr/bin/env python3
"""Named probe 2: unlocked control — client stopped, rollback must succeed.

Isolates the lock as the variable. Live run must restore uniform V1 and the
artifact must carry the matching post-rollback inventory.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from lab import run_suite  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0046-locked-file-rollback.json"
SENTINEL = (
    "SUCCESS:CNF-0046 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both the locked and "
    "unlocked runs completed and the resulting version inventories are "
    "attached. Any other terminal state is FAILED:CNF-0046 <classification> "
    "with the diagnostic tail attached."
)


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0046-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "CNF-0046":
        print("FAILED:CNF-0046-probe2 unit_id", doc.get("unit_id"))
        return 1
    if SENTINEL not in ART.read_text(encoding="utf-8"):
        print("FAILED:CNF-0046-probe2 sentinel absent")
        return 1

    suite = run_suite()
    unlocked = suite["unlocked"]
    locked = suite["locked_aware"]

    if unlocked.get("exit_code") != 0:
        print("FAILED:CNF-0046-probe2 unlocked exit", unlocked.get("exit_code"))
        return 1
    if not unlocked.get("all_v1"):
        print("FAILED:CNF-0046-probe2 unlocked did not restore uniform v1")
        return 1
    if unlocked.get("mixed_version") or unlocked.get("corrupted"):
        print("FAILED:CNF-0046-probe2 unlocked mixed or corrupt")
        return 1
    if locked.get("exit_code") == 0:
        print("FAILED:CNF-0046-probe2 lock was not the isolating variable")
        return 1

    inv = doc.get("inventories") or {}
    post_u = {r["path"]: r for r in (inv.get("post_unlocked_control") or {}).get("files") or []}
    v1 = (inv.get("known_hashes") or {}).get("v1") or {}
    if not post_u or not v1:
        print("FAILED:CNF-0046-probe2 artifact unlocked inventory missing")
        return 1
    for rel, sha in v1.items():
        row = post_u.get(rel) or {}
        if row.get("sha256") != sha or row.get("version") != "v1":
            print(f"FAILED:CNF-0046-probe2 artifact post_unlocked drift {rel}")
            return 1

    unlocked_run = doc.get("unlocked_run") or {}
    if unlocked_run.get("exit_code") != 0:
        print("FAILED:CNF-0046-probe2 artifact unlocked_run exit drift")
        return 1
    if not (doc.get("inventories") or {}).get("post_locked_aware"):
        print("FAILED:CNF-0046-probe2 locked inventory missing from artifact")
        return 1

    out = {
        "probe": "probe2-unlocked",
        "unit_id": "CNF-0046",
        "pass": True,
        "unlocked_exit": unlocked["exit_code"],
        "all_v1": True,
        "locked_exit": locked["exit_code"],
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"unlocked_exit={unlocked['exit_code']} all_v1={unlocked['all_v1']} "
        f"locked_exit={locked['exit_code']}"
    )
    print("SUCCESS:CNF-0046-probe2 unlocked control isolates the lock")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
