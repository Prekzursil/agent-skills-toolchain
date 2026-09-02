#!/usr/bin/env python3
"""Probe 2: os.scandir oracle independent of barrier reporting.

A barrier that reports the file exists is contradicted when scandir of the
output root does not list the expected name. Windows Output.json vs
output.json is classified explicitly, not silently accepted.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from injection import UNIT, run_campaign  # noqa: E402

SENTINEL = f"SUCCESS:{UNIT}-probe2"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    camp = run_campaign()
    checks = camp["checks"]
    case = camp["case_collision"]
    mutant_missing = next(r for r in camp["mutant_rows"] if r["kind"] == "missing")
    payload = {
        "unit_id": UNIT,
        "probe": "probe2-scandir-oracle",
        "method": camp["method_probe2"],
        "used_os_scandir": True,
        "used_barrier_reporting_as_oracle": False,
        "checks": {
            "missing_scandir_lacks_expected_artifact": checks[
                "missing_scandir_lacks_expected_artifact"
            ],
            "valid_scandir_has_expected_artifact": checks[
                "valid_scandir_has_expected_artifact"
            ],
            "production_agrees_with_scandir": checks["production_agrees_with_scandir"],
            "mutant_exists_claim_contradicted_by_scandir": checks[
                "mutant_exists_claim_contradicted_by_scandir"
            ],
            "case_collision_classified_explicitly": checks[
                "case_collision_classified_explicitly"
            ],
        },
        "listings": {
            k: {
                "expected_artifact_present": camp["trees"][k][
                    "expected_artifact_present"
                ],
                "file_reprs": camp["trees"][k]["file_reprs"],
                "names": [row["name"] for row in camp["trees"][k]["listing"]],
            }
            for k in camp["trees"]
        },
        "mutant_missing": {
            "recorded_complete": mutant_missing["recorded_complete"],
            "claims_artifact_exists": mutant_missing["claims_artifact_exists"],
            "scandir_contradicts_exists_claim": mutant_missing[
                "scandir_contradicts_exists_claim"
            ],
            "expected_artifact_present": mutant_missing["expected_artifact_present"],
        },
        "case_collision": case,
        "pass": camp["pass"],
    }
    print(json.dumps(payload, sort_keys=True))
    if payload["method"] != "os.scandir-independent-filesystem-oracle":
        return fail("probe 2 method is not os.scandir")
    if not checks["missing_scandir_lacks_expected_artifact"]:
        return fail("scandir listed output.json after the missing worker")
    if not checks["valid_scandir_has_expected_artifact"]:
        return fail("scandir missed output.json after the valid worker")
    if not checks["production_agrees_with_scandir"]:
        return fail("production barrier verdict disagrees with scandir")
    if not checks["mutant_exists_claim_contradicted_by_scandir"]:
        return fail("scandir did not contradict the mutant exists-claim")
    if case.get("silently_accepted") is True:
        return fail("case-collision variant was silently accepted")
    if not checks["case_collision_classified_explicitly"]:
        return fail("case-collision was not classified explicitly")
    if not camp["pass"]:
        return fail(f"campaign checks {checks}")
    print(
        "scandir_missing_absent=True scandir_valid_present=True "
        "mutant_contradicted=True case={c}".format(c=case["classification"])
    )
    print(f"{SENTINEL} scandir oracle contradicts mutant exists-claim")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
