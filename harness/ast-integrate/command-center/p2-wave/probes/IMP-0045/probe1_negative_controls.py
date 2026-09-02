#!/usr/bin/env python3
"""Probe 1: green fixture + 7 distinct negative-control codes + unit tests."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from loader import PLUGIN, SENTINEL, load_mod, load_receipt  # noqa: E402

B = load_mod("blob")
F = load_mod("fixture_tree")
C = load_mod("conformance")


def run_files(files: dict) -> dict:
    td = Path(tempfile.mkdtemp(prefix="imp0045-p1-"))
    git_dir, tree = F.build_tree(files, td)
    return C.run_conformance(git_dir, tree)


def main() -> int:
    rec = load_receipt()
    if rec.get("unit_id") != "IMP-0045":
        print("FAILED:IMP-0045-probe1 unit_id", rec.get("unit_id"))
        return 1

    good = run_files(F.good_files())
    if good["verdict"] != "PASS" or good["violations"]:
        print("FAILED:IMP-0045-probe1 good fixture not PASS")
        print(json.dumps(good["violations"], indent=2)[:2000])
        return 1
    if good["hash_route"] != C.HASH_ROUTE:
        print("FAILED:IMP-0045-probe1 hash_route", good["hash_route"])
        return 1

    seen: list[str] = []
    rows = []
    for code, how, fn in F.MUTATIONS:
        report = run_files(fn(F.good_files()))
        codes = [v["code"] for v in report["violations"]]
        hit = code in codes
        rows.append({"expected": code, "how": how, "hit": hit, "codes": codes})
        if not hit or report["verdict"] != "FAIL":
            print(f"FAILED:IMP-0045-probe1 mutation {code} not caught {codes}")
            return 1
        seen.append(code)
    if len(seen) < 6 or len(set(seen)) != len(seen):
        print("FAILED:IMP-0045-probe1 codes not distinct", seen)
        return 1

    loader = unittest.TestLoader()
    suite = loader.discover(str(PLUGIN / "tests"), pattern="test_conformance.py")
    result = unittest.TextTestRunner(verbosity=1, stream=sys.stdout).run(suite)
    if not result.wasSuccessful():
        print(
            f"FAILED:IMP-0045-probe1 unittest failures={len(result.failures)} "
            f"errors={len(result.errors)}"
        )
        return 1

    summary = {
        "probe": "probe1-negative-controls",
        "unit_id": "IMP-0045",
        "good_pass": True,
        "hash_route": good["hash_route"],
        "verdict_digest": good["verdict_digest"],
        "mutations": rows,
        "distinct_codes": seen,
        "unittest_run": result.testsRun,
        "pass": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print(f"good_pass=True mutations={len(rows)} distinct={len(set(seen))}")
    print(f"SUCCESS:IMP-0045-probe1 negative controls and {SENTINEL} tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
