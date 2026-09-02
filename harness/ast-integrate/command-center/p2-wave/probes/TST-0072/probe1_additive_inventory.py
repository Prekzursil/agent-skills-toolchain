#!/usr/bin/env python3
"""Named probe 1: additive restore keeps user-owned paths and restores v1."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from host import host_census  # noqa: E402
from scenario import detector_control, rehearse  # noqa: E402


def _fail(msg: str) -> int:
    print(f"FAILED:TST-0072-probe1 {msg}")
    return 1


def main() -> int:
    host_before = host_census()
    with tempfile.TemporaryDirectory(prefix="tst0072-p1-") as tmp:
        root = Path(tmp)
        result = rehearse(root / "additive", "additive")
        control = detector_control(root / "detect")
    host_after = host_census()

    if host_before != host_after:
        return _fail("host fingerprint changed")
    tests = result["tests"]
    if not tests["all_pass"]:
        print(json.dumps(tests, indent=2))
        return _fail("additive tests did not all pass")
    if result["delta"]["user_deleted"]:
        return _fail(f"user paths deleted {result['delta']['user_deleted']}")
    if not result["user_owned_inside_managed_tree"]:
        return _fail("fixture did not plant user-owned paths inside the tree")
    if not control["detected"]:
        return _fail(f"extra-file control silent extras={control['extras']}")

    t1 = tests["test_rollback_restores_prior_version"]
    t2 = tests["test_rollback_deletes_zero_user_owned_paths"]
    t3 = tests["test_command_inventory_is_unchanged_after_rollback"]
    out = {
        "probe": "probe1-additive-inventory",
        "unit_id": "TST-0072",
        "mode": "additive",
        "user_owned_inside_managed_tree": True,
        "user_owned_count": result["user_owned_count"],
        "user_deleted": result["delta"]["user_deleted"],
        "prior_restored": t1["prior_bytes_restored"],
        "zero_user_deletes": t2["pass"],
        "commands_preserved": t3["pass"],
        "detector_control": control,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"user_inside_tree=True user_deleted=0 prior_restored={t1['prior_bytes_restored']} "
        f"commands_preserved={t3['pass']} extra_detected={control['detected']}"
    )
    print("SUCCESS:TST-0072-probe1 additive restore; zero user-owned deletions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
