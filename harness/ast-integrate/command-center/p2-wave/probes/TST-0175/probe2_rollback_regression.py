#!/usr/bin/env python3
"""Probe 2: regression seed 11347 — rollback must not drop commands or user data.

Correct rollback is a set difference (package blobs only). A wholesale snapshot
restore in the same run must go red, proving the detector is not a rubber stamp.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402


def fail(msg: str, extra=None) -> int:
    print(f"FAILED:TST-0175-probe2 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, default=str)[:4000])
    return 1


def main() -> int:
    doc = S.require_receipt()
    with tempfile.TemporaryDirectory(prefix="tst0175-p2-") as tmp:
        measured = S.measure_rollback(Path(tmp))
    good = measured["correct"]
    naive = measured["naive_wholesale"]
    print(
        json.dumps(
            {
                "probe": "probe2-rollback-regression-11347",
                "unit_id": "TST-0175",
                "correct_exit": good["exit_code"],
                "correct_user_tree_identical": good["user_tree_identical"],
                "correct_user_file": good["user_file"]["exists"],
                "correct_user_cmd": good["user_cmd"]["exists"],
                "naive_user_file": measured["naive_user_file"]["exists"],
                "naive_user_cmd": measured["naive_user_cmd"]["exists"],
                "naive_user_identical": naive.get("user_data_byte_identical"),
            },
            sort_keys=True,
        )
    )
    if good["exit_code"] != 0:
        return fail("rollback CLI", good)
    if not good["user_tree_identical"]:
        return fail("correct rollback changed user-data tree hash", good)
    if not good["user_file"]["exists"] or not good["user_cmd"]["exists"]:
        return fail("correct rollback dropped user data or commands", good)
    if not good["pkg"]["exists"]:
        return fail("correct rollback failed to restore package blob", good)
    if measured["naive_user_file"]["exists"] or measured["naive_user_cmd"]["exists"]:
        return fail(
            "wholesale-snapshot mutant kept user files; 11347 detector is silent",
            measured,
        )
    if naive.get("user_data_byte_identical"):
        return fail("naive rollback reported user-data identity", naive)
    if str(doc.get("state") or "").upper() != "SUCCESS":
        return fail("receipt state", doc.get("state"))
    print(
        "SUCCESS:TST-0175-probe2 rollback preserves user data; "
        "naive snapshot restore reproduces 11347"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
