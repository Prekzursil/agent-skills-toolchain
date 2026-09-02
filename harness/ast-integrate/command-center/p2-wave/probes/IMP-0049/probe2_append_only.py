#!/usr/bin/env python3
"""Named probe 2: append-only rejection, omit-step negative control, interrupted run.

Mechanically different from probe 1:
  * mutates the ledger API and the on-disk JSONL
  * replays an intentionally incomplete inverse list
  * leaves a started record without an applied marker
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

from hash_census import census_diff, hash_census  # noqa: E402
from legacy_layout_steps import (  # noqa: E402
    FROM_VERSION,
    STEP_IDS,
    TO_VERSION,
    recorded_steps,
    seed_legacy_tree,
)
from migration_ledger import (  # noqa: E402
    AppendOnlyError,
    LedgerIntegrityError,
    MigrationLedger,
    apply_preimage,
    compute_record_hash,
    replay_and_compare,
    run_recorded_steps,
)

ART = REPO / "command-center/receipts/IMP-0049.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:IMP-0049-probe2 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:IMP-0049" not in text:
        print("FAILED:IMP-0049-probe2 sentinel absent")
        return 1

    with tempfile.TemporaryDirectory(prefix="imp0049-p2-") as tmp:
        root = Path(tmp) / "plugin-home"
        seed_legacy_tree(root)
        ledger_path = Path(tmp) / "migration-ledger.jsonl"
        ledger = MigrationLedger(ledger_path, machine="probe2")
        result = run_recorded_steps(
            root,
            ledger,
            recorded_steps(),
            from_version=FROM_VERSION,
            to_version=TO_VERSION,
        )
        inverses = ledger.inverses_for_run(result["run_id"])
        omitted = [r for r in inverses if r["step_id"] != STEP_IDS[1]]
        if len(omitted) != 2:
            print(f"FAILED:IMP-0049-probe2 omit filter produced {len(omitted)}")
            return 1

        incomplete = Path(tmp) / "omit-one"
        shutil.copytree(root, incomplete)
        for rec in reversed(omitted):
            apply_preimage(incomplete, rec["inverse"])
        omit_diff = census_diff(result["pre_census"], hash_census(incomplete))
        if omit_diff["equal"]:
            print("FAILED:IMP-0049-probe2 omit-step still matched prior census")
            return 1

        complete = Path(tmp) / "full-replay"
        shutil.copytree(root, complete)
        full = replay_and_compare(
            complete, ledger, result["run_id"], result["pre_census"]
        )
        if not full["equal"]:
            print("FAILED:IMP-0049-probe2 full replay should match (silent-on-good)")
            print(json.dumps(full["diff"], indent=2)[:2000])
            return 1

        before = ledger_path.read_bytes()
        append_only_rejected = 0
        for call in (
            lambda: ledger.replace_record(1, {"seq": 1, "step_id": "forged"}),
            lambda: ledger.rewrite_all([]),
            lambda: ledger.truncate(),
        ):
            try:
                call()
            except AppendOnlyError:
                append_only_rejected += 1
            else:
                print("FAILED:IMP-0049-probe2 in-place edit was accepted")
                return 1
        if ledger_path.read_bytes() != before:
            print("FAILED:IMP-0049-probe2 ledger bytes changed after rejected edits")
            return 1

        mutated = before.decode("utf-8").replace(
            "copied-skills-to-marketplace", "copied-skills-FORGED", 1
        )
        tampered = Path(tmp) / "tampered.jsonl"
        tampered.write_text(mutated, encoding="utf-8")
        chain_fired = False
        try:
            MigrationLedger.load(tampered)
        except LedgerIntegrityError:
            chain_fired = True
        if not chain_fired:
            print("FAILED:IMP-0049-probe2 hash chain accepted a hex-edit")
            return 1

        crash_root = Path(tmp) / "crash-home"
        seed_legacy_tree(crash_root)
        crash_ledger = MigrationLedger(Path(tmp) / "crash-ledger.jsonl", machine="probe2")
        crash = run_recorded_steps(
            crash_root,
            crash_ledger,
            recorded_steps(),
            from_version=FROM_VERSION,
            to_version=TO_VERSION,
            complete=False,
        )
        loaded = MigrationLedger.load(Path(tmp) / "crash-ledger.jsonl", machine="probe2")
        last = loaded.records[-1]
        if last["status"] != "started":
            print("FAILED:IMP-0049-probe2 interrupted last status", last["status"])
            return 1
        if last["record_hash"] != compute_record_hash(last):
            print("FAILED:IMP-0049-probe2 partial record hash invalid")
            return 1
        if last.get("inverse") is None:
            print("FAILED:IMP-0049-probe2 started record missing inverse")
            return 1
        crash_replay = replay_and_compare(
            crash_root, loaded, crash["run_id"], crash["pre_census"]
        )
        if not crash_replay["equal"]:
            print("FAILED:IMP-0049-probe2 interrupted inverse replay mismatch")
            print(json.dumps(crash_replay["diff"], indent=2)[:2000])
            return 1

        payload = {
            "pass": True,
            "probe": "probe2-append-only-omit-interrupted",
            "unit_id": "IMP-0049",
            "omit_step_mismatch": True,
            "omit_changed": omit_diff["changed"],
            "omit_missing": omit_diff["missing"],
            "omit_extra": omit_diff["extra"],
            "full_replay_equal": True,
            "append_only_rejected": append_only_rejected,
            "hash_chain_detects_hex_edit": True,
            "interrupted_last_status": last["status"],
            "interrupted_records": len(loaded.records),
            "interrupted_replay_equal": True,
        }
        print(json.dumps(payload, sort_keys=True))
        print(
            f"omit_mismatch=True full_equal=True append_only_rejected={append_only_rejected} "
            f"chain_fired=True interrupted_started={last['status']} crash_restored=True"
        )
        print("SUCCESS:IMP-0049-probe2 append-only, omit-step control, interrupted records")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
