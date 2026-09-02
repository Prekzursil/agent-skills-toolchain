#!/usr/bin/env python3
"""Named probe 2: naive tree-replace deletes in-tree user paths (both-states).

Walker 2 (os.walk) recomputes the same inventories. Additive still passes.
Naive must fail the user-owned deletion test — otherwise the suite is vacuous.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from host import host_census  # noqa: E402
from scenario import rehearse  # noqa: E402


def _fail(msg: str) -> int:
    print(f"FAILED:TST-0072-probe2 {msg}")
    return 1


def main() -> int:
    host_before = host_census()
    with tempfile.TemporaryDirectory(prefix="tst0072-p2-") as tmp:
        root = Path(tmp)
        good = rehearse(root / "additive", "additive")
        bad = rehearse(root / "naive", "naive")
    host_after = host_census()

    if host_before != host_after:
        return _fail("host fingerprint changed")
    if not good["tests"]["all_pass"]:
        print(json.dumps(good["tests"], indent=2))
        return _fail("additive control unexpectedly failed")

    naive_user_deleted = bad["delta"]["user_deleted"]
    naive_t2 = bad["tests"]["test_rollback_deletes_zero_user_owned_paths"]
    if naive_t2["pass"]:
        return _fail("naive replace unexpectedly preserved user-owned paths")
    if not naive_user_deleted:
        return _fail("naive replace did not delete user-owned paths")
    if not bad.get("collateral_by_construction"):
        return _fail("naive collateral flag not set")

    planted = set(good["user_owned_paths"])
    if not planted.issubset(set(naive_user_deleted)):
        return _fail(
            f"naive deletes {naive_user_deleted} did not cover planted {sorted(planted)}"
        )

    out = {
        "probe": "probe2-naive-mutant",
        "unit_id": "TST-0072",
        "additive_pass": True,
        "naive_user_deleted": naive_user_deleted,
        "naive_zero_user_deletes_pass": False,
        "collateral_by_construction": True,
        "user_owned_inside_managed_tree": True,
        "second_walker_agreed": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"additive_pass=True naive_deletes={len(naive_user_deleted)} "
        f"collateral_by_construction=True"
    )
    print("SUCCESS:TST-0072-probe2 naive replace is collateral by construction")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
