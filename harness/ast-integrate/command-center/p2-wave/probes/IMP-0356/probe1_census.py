#!/usr/bin/env python3
"""Named probe 1: required-output census over 20 recorded councils.

Each row lists missing (absent or vacuous) outputs. Ranking answers which
required output is incomplete most often. Presence-only is not a pass.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.outcomes.completeness import (  # noqa: E402
    census,
    check_artifact,
    load_recorded_fixtures,
)

FIXTURE_DIR = HERE / "fixtures" / "recorded"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0356-probe1 {msg}")
    return 1


def main() -> int:
    corpus = load_recorded_fixtures(FIXTURE_DIR)
    if len(corpus) != 20:
        return fail(f"expected 20 recorded councils, got {len(corpus)}")
    on_disk = sorted(p.name for p in FIXTURE_DIR.glob("rec-*.json"))
    if len(on_disk) != 20:
        return fail(f"fixture files on disk: {on_disk}")

    report = census(corpus)
    if report["n_councils"] != 20:
        return fail(f"census n={report['n_councils']}")
    if report["n_pass"] + report["n_fail"] != 20:
        return fail("pass+fail does not cover the corpus")
    if report["missing_most_often"] != "calibration":
        return fail(f"most-often incomplete={report['missing_most_often']}")

    by_id = {row["council_id"]: row for row in report["rows"]}
    rec01 = by_id.get("rec-01") or {}
    if rec01.get("pass"):
        return fail("rec-01 (missing calibration+experiments) passed")
    if "calibration" not in rec01.get("missing", []):
        return fail(f"rec-01 missing not listed: {rec01.get('missing')}")
    rec20 = by_id.get("rec-20") or {}
    if not rec20.get("pass") or rec20.get("missing"):
        return fail(f"complete rec-20 failed: {rec20}")
    rec15 = by_id.get("rec-15") or {}
    if not rec15.get("present", {}).get("unknowns"):
        return fail("rec-15 unknowns key should be present")
    if not rec15.get("vacuous", {}).get("unknowns"):
        return fail("rec-15 TBD unknowns should be vacuous")
    if "unknowns" not in rec15.get("missing", []):
        return fail("vacuous unknowns not listed as missing")

    live = check_artifact(corpus[-1])
    if corpus[-1]["council_id"] == "rec-20" and not live["pass"]:
        return fail("disk rec-20 does not pass check_artifact")

    ranked = report["per_output"]
    cal = next(r for r in ranked if r["output"] == "calibration")
    if cal["incomplete"] != 12 or cal["absent"] != 10 or cal["vacuous"] != 2:
        return fail(f"calibration ranking {cal}")

    payload = {
        "probe": "probe1-census",
        "unit_id": "IMP-0356",
        "n_councils": report["n_councils"],
        "n_pass": report["n_pass"],
        "n_fail": report["n_fail"],
        "missing_most_often": report["missing_most_often"],
        "per_output": ranked,
        "rows": [
            {
                "council_id": row["council_id"],
                "pass": row["pass"],
                "missing": row["missing"],
                "fail_reasons": row["fail_reasons"],
            }
            for row in report["rows"]
        ],
        "fixture_dir": str(FIXTURE_DIR.relative_to(REPO)).replace("\\", "/"),
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"n=20 fail={report['n_fail']} most={report['missing_most_often']} "
        f"cal_incomplete={cal['incomplete']}"
    )
    print("SUCCESS:IMP-0356-probe1 census over 20 recorded councils; missing listed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
