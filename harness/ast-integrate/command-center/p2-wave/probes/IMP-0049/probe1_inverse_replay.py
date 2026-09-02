#!/usr/bin/env python3
"""Named probe 1: two independent signals on a live migration run.

Signal 1: the ledger's recorded step list after apply.
Signal 2: hash census of a tree restored by replaying ONLY recorded inverses
          versus the pre-migration snapshot.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN))

from hash_census import hash_census  # noqa: E402
from legacy_layout_steps import (  # noqa: E402
    FROM_VERSION,
    STEP_IDS,
    TO_VERSION,
    recorded_steps,
    seed_legacy_tree,
)
from migration_ledger import (  # noqa: E402
    MigrationLedger,
    replay_and_compare,
    run_recorded_steps,
)

ART = REPO / "command-center/receipts/IMP-0049.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:IMP-0049-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != "IMP-0049":
        print("FAILED:IMP-0049-probe1 unit_id", doc.get("unit_id"))
        return 1
    if "SUCCESS:IMP-0049" not in text:
        print("FAILED:IMP-0049-probe1 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:IMP-0049-probe1 self-declared", doc.get("state"))
        return 1

    with tempfile.TemporaryDirectory(prefix="imp0049-p1-") as tmp:
        root = Path(tmp) / "plugin-home"
        seed_legacy_tree(root)
        ledger = MigrationLedger(Path(tmp) / "migration-ledger.jsonl", machine="probe1")
        result = run_recorded_steps(
            root,
            ledger,
            recorded_steps(),
            from_version=FROM_VERSION,
            to_version=TO_VERSION,
        )
        step_list = result["step_ids"]
        if tuple(step_list) != STEP_IDS:
            print(f"FAILED:IMP-0049-probe1 step_list={step_list} want={list(STEP_IDS)}")
            return 1
        if result["pre_census"] == result["post_census"]:
            print("FAILED:IMP-0049-probe1 migration was a no-op; census unchanged")
            return 1

        restored = Path(tmp) / "restored"
        shutil.copytree(root, restored)
        report = replay_and_compare(
            restored, ledger, result["run_id"], result["pre_census"]
        )
        if not report["equal"]:
            print("FAILED:IMP-0049-probe1 inverse replay census mismatch")
            print(json.dumps(report["diff"], indent=2)[:2000])
            return 1
        if hash_census(restored) != result["pre_census"]:
            print("FAILED:IMP-0049-probe1 restored census object inequality")
            return 1

        n_started = sum(1 for r in ledger.records if r["status"] == "started")
        n_applied = sum(1 for r in ledger.records if r["status"] == "applied")
        payload = {
            "pass": True,
            "probe": "probe1-inverse-replay",
            "unit_id": "IMP-0049",
            "run_id": result["run_id"],
            "recorded_step_list": step_list,
            "records": len(ledger.records),
            "started": n_started,
            "applied": n_applied,
            "pre_files": len(result["pre_census"]),
            "post_files": len(result["post_census"]),
            "restored_equal": True,
            "census_changed_by_apply": True,
        }
        print(json.dumps(payload, sort_keys=True))
        print(
            f"steps={step_list} started={n_started} applied={n_applied} "
            f"pre={len(result['pre_census'])} post={len(result['post_census'])} restored_equal=True"
        )
        print("SUCCESS:IMP-0049-probe1 recorded step list and inverse-replay census")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
