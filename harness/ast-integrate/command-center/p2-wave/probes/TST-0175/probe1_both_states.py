#!/usr/bin/env python3
"""Probe 1: planted user file survives; planted derived-cache file is removed.

Both states in one run: ownership-aware update/repair vs a no-ownership mutant.
Independent signals: (a) user-data tree hash pre/post, (b) owned cache emptiness.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

USER = S.USER_FILE
CMD = S.USER_CMD
CACHE = S.OWNED_CACHE
INDEX = S.OWNED_INDEX
FOREIGN = S.FOREIGN_CACHE


def fail(msg: str, extra=None) -> int:
    print(f"FAILED:TST-0175-probe1 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, default=str)[:4000])
    return 1


def main() -> int:
    doc = S.require_receipt()
    with tempfile.TemporaryDirectory(prefix="tst0175-p1-") as tmp:
        measured = S.measure_repair_and_update(Path(tmp))
    want = measured["planted_sha256"]
    repair = measured["repair"]
    update = measured["update"]
    print(
        json.dumps(
            {
                "probe": "probe1-both-states-owned-cache-invalidation",
                "unit_id": "TST-0175",
                "repair_exit": repair["exit_code"],
                "update_exit": update["exit_code"],
                "repair_user_tree_identical": repair["user_tree_identical"],
                "update_user_tree_identical": update["user_tree_identical"],
                "owned_cache_removed": not repair["owned_cache"]["exists"],
                "foreign_cache_survived": repair["foreign_cache"]["exists"],
                "mutant_user_file_exists": measured["mutant_user_file"]["exists"],
                "missing_manifest_ok": measured["missing_manifest"]["ok"],
            },
            sort_keys=True,
        )
    )

    if repair["exit_code"] != 0:
        return fail("install --repair CLI", repair)
    if update["exit_code"] != 0:
        return fail("update CLI", update)
    if not repair["user_tree_identical"] or not update["user_tree_identical"]:
        return fail("user-data tree hash changed", measured)
    for row in (repair, update):
        if not row["user_file"]["exists"] or row["user_file"]["sha256"] != want[USER]:
            return fail("planted user file did not survive byte-identical", row)
        if row["owned_cache"]["exists"]:
            return fail("planted derived-cache file was not removed", row)
        if not row["foreign_cache"]["exists"] or row["foreign_cache"]["sha256"] != want[FOREIGN]:
            return fail("foreign cache not on the ownership list was mutated", row)
    if not repair["user_cmd"]["exists"] or repair["user_cmd"]["sha256"] != want[CMD]:
        return fail("user command mutated by repair", repair)
    if repair["owned_index"]["exists"]:
        return fail("owned index cache survived repair", repair)
    if measured["mutant_user_file"]["exists"] or measured["mutant_no_ownership"][
        "user_data_byte_identical"
    ]:
        return fail("no-ownership mutant did not destroy user data", measured["mutant_no_ownership"])
    if measured["missing_manifest"]["ok"] or not measured["missing_manifest"]["refused"]:
        return fail("missing ownership manifest must refuse", measured["missing_manifest"])
    if not repair["user_tree_before"] or repair["user_tree_before"] != repair["user_tree_after"]:
        return fail("signal (a) user-data tree hash", repair)
    if repair["owned_cache"]["exists"] or repair["owned_index"]["exists"]:
        return fail("signal (b) owned cache not empty", repair)
    if str(doc.get("report_kind") or "") != "cache_report":
        return fail("receipt report_kind", doc.get("report_kind"))
    print(
        "SUCCESS:TST-0175-probe1 both-states user-file-survives owned-cache-removed "
        "mutant-red missing-manifest-refuses"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
