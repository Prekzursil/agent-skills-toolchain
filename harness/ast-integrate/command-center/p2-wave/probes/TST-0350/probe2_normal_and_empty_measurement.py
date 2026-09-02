#!/usr/bin/env python3
"""Probe 2: normal run stays green; empty-input measurement FAILS.

Required proofs:
  * Full 4-test fixture with min=3 (and min=4) PASSES — the floor is not a
    nuisance gate on a healthy collection.
  * Empty-input rule on a non-test measurement: file census of an empty
    directory and meaningless_green_mean([]) are errors under the floor, never
    a pass. A non-empty census and floored_mean([2,4]) stay green.
  * TEST-REGISTRY.json: every registered suite has a declared minimum and the
    observed AST collected count matches it. An unregistered tools/**/test_*.py
    is itself a finding.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SUITE = HERE / "fixtures" / "suite"
ART = REPO / "command-center/receipts/TST-0350.json"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})

sys.path.insert(0, str(REPO / "tools" / "command-center"))
import suitefloor as F  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:TST-0350-probe2 {msg}")
    return 1


def main() -> int:
    full = F.run_unittest_cli(SUITE, ["discover", "-s", str(SUITE), "-p", "test*.py"])
    print(json.dumps({"normal_run": {"rc": full["rc"], "collected": full["collected"]}}, sort_keys=True))
    if full["rc"] != 0:
        return fail(f"normal fixture run rc={full['rc']}")
    if int(full["collected"]) != 4:
        return fail(f"normal fixture collected {full['collected']}, want 4")
    for minimum in (3, 4):
        floor = F.evaluate(
            collected=int(full["collected"]),
            min_collected=minimum,
            runner_exit_code=int(full["rc"]),
            runner_was_successful=True,
        )
        if floor["verdict"] != "PASS":
            return fail(f"healthy run failed the floor at min={minimum}: {floor}")
        if floor["reasons"]:
            return fail(f"healthy run carried reasons {floor['reasons']}")

    with tempfile.TemporaryDirectory(prefix="tst0350-census-empty-") as tmp:
        empty_paths = F.census_files(Path(tmp))
    if empty_paths:
        return fail(f"empty census was not empty: {empty_paths}")
    empty_failed = False
    try:
        F.require_nonempty(empty_paths, label="file-census")
    except F.EmptyCollectionError as exc:
        empty_failed = True
        print(f"empty_census_error={exc}")
    if not empty_failed:
        return fail("empty file-census did not fail closed")

    populated = F.census_files(SUITE)
    filled = F.require_nonempty(populated, label="file-census")
    if "test_demo.py" not in filled:
        return fail(f"populated census missed test_demo.py: {filled}")

    if F.meaningless_green_mean([]) != 0.0:
        return fail("empty-input benchmark did not return the meaningless 0.0 green")
    if F.floored_mean([2.0, 4.0]) != 3.0:
        return fail("non-empty benchmark was perturbed by the floor")
    bench_failed = False
    try:
        F.floored_mean([])
    except F.EmptyCollectionError:
        bench_failed = True
    if not bench_failed:
        return fail("empty-input benchmark was a pass")

    checked = F.check_registry(REPO)
    print(json.dumps({"registry_ok": checked["ok"], "suite_count": len(checked["suites"]), "findings": checked["findings"]}, sort_keys=True))
    if not checked["ok"]:
        return fail(f"registry findings {checked['findings']}")
    if not checked["suites"]:
        return fail("registry contained no suites")
    for row in checked["suites"]:
        if row["declared_minimum"] is None:
            return fail(f"suite {row['path']} has no declared minimum")
        if row["observed_collected"] != row["declared_minimum"]:
            return fail(
                f"{row['path']} declared {row['declared_minimum']} observed {row['observed_collected']}"
            )
        if row["verdict"] != "PASS":
            return fail(f"{row['path']} floor {row['verdict']} {row['reasons']}")

    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        if str(doc.get("state") or "").upper() in NOT_DELIVERING:
            return fail(f"self-declared {doc.get('state')}")
        if "SUCCESS:TST-0350" not in text:
            return fail("receipt sentinel-absent")

    print("normal_run_passes=True empty_measurement_fails=True registry_mins_match=True")
    print("SUCCESS:TST-0350-probe2 normal run passes; empty census/benchmark fail closed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
