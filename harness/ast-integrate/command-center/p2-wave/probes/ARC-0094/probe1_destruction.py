#!/usr/bin/env python3
"""Named probe 1: destruction control with a planted owner-authored file.

A naive tree-sync to the pre-change backup DELETES the planted file.
The contract engine must REFUSE that rollback, leave the file in place,
apply no mutations, and emit a schema-valid refused record. A forged
complete=true record for the same event must be schema-invalid.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import emit_contract as C  # noqa: E402
import engine as E  # noqa: E402
import scenario as S  # noqa: E402

GARBAGE = (
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
    {},
)


def fail(msg: str) -> int:
    print(f"FAILED:ARC-0094-probe1 {msg}")
    return 1


def main() -> int:
    C.write_schema()
    schema = json.loads((REPO / C.OUT_REL).read_text(encoding="utf-8"))
    try:
        Draft202012Validator.check_schema(schema)
    except Exception as exc:  # noqa: BLE001
        return fail(f"check_schema {type(exc).__name__}: {exc}")
    validator = Draft202012Validator(schema)
    for i, probe in enumerate(GARBAGE):
        if not list(validator.iter_errors(probe)):
            return fail(f"schema accepted garbage[{i}]")

    with tempfile.TemporaryDirectory(prefix="arc0094-p1-") as tmp:
        root = Path(tmp)
        live = root / "live"
        backup_root = root / "backup"
        naive = root / "naive"
        S.write_previous_tree(live)
        E.copy_tree(live, backup_root)
        backup = E.snapshot(backup_root)
        if not backup.get("captured_before_mutation"):
            return fail("backup not marked captured_before_mutation")
        S.apply_upgrade(live)
        planted = S.plant_owner_file(live)
        planted_rel = S.OWNER_PLANTED_REL
        if not planted.is_file():
            return fail("planted owner file missing")

        naive_deletes = E.naive_tree_sync_deletes(live, backup)
        if planted_rel not in naive_deletes:
            return fail(f"naive plan did not target planted file: {naive_deletes}")

        E.copy_tree(live, naive)
        deleted = E.apply_naive_tree_sync(naive, backup_root, backup)
        if planted_rel not in deleted:
            return fail(f"naive sync did not delete planted file: {deleted}")
        if (naive / planted_rel).is_file():
            return fail("naive sync left planted file in place (control silent)")

        pre_version = (live / S.VERSION_REL).read_text(encoding="utf-8")
        result = E.rollback_once(live, backup_root, backup, planted_rel=planted_rel)
        if result.outcome != "REFUSED_WOULD_DESTROY_OWNER_AUTHORED":
            return fail(f"expected refuse, got {result.outcome} {result.reason}")
        if result.complete:
            return fail("refused rollback marked complete")
        if result.mutations_applied:
            return fail("refused rollback applied mutations")
        if not result.would_destroy_owner_authored:
            return fail("would_destroy_owner_authored was false")
        if planted_rel not in result.owner_paths_that_would_be_deleted:
            return fail("planted path missing from owner delete plan")
        if not (live / planted_rel).is_file():
            return fail("engine destroyed the planted owner file")
        if (live / S.VERSION_REL).read_text(encoding="utf-8") != pre_version:
            return fail("engine mutated version.json on refuse")

        record = E.record_from_result(result)
        rec_errs = list(validator.iter_errors(record))
        if rec_errs:
            return fail(f"refused record schema-invalid: {rec_errs[0].message}")

        forged = json.loads(json.dumps(record))
        forged["complete"] = True
        forged["outcome"] = "COMPLETE"
        forged["post_restore_verification"]["passed"] = True
        if not list(validator.iter_errors(forged)):
            return fail("schema accepted complete=true while would_destroy is true")

    out = {
        "probe": "probe1-destruction-control",
        "unit_id": "ARC-0094",
        "naive_would_delete_planted": True,
        "naive_deleted_on_copy": True,
        "engine_refused": True,
        "planted_survived": True,
        "mutations_applied": False,
        "schema_rejects_garbage": True,
        "schema_rejects_forged_complete": True,
        "schema_accepts_refuse_record": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        "planted_owner_file=owner/planted-owner-file.md "
        "naive_deletes=True engine_refused=True survived=True"
    )
    print("SUCCESS:ARC-0094-probe1 destruction control planted owner file")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
