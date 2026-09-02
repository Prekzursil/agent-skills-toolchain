#!/usr/bin/env python3
"""Named probe 2: reviewer re-runs detector controls on known-broken fixtures.

A blueprint that loads but produces no artifact must be a failure.
Filesystem enumeration must still see a disk file the catalog omitted.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import sweep as S  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0077-blueprint-executability.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0077-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "CNF-0077":
        print("FAILED:CNF-0077-probe2 unit_id", doc.get("unit_id"))
        return 1

    controls = S.detector_controls()
    if not controls["pass"]:
        print("FAILED:CNF-0077-probe2 detector control did not pass")
        print(json.dumps({k: v for k, v in controls.items() if k != "rows"}, indent=2)[:4000])
        return 1
    if not controls["fired_on_bad_state"]:
        print("FAILED:CNF-0077-probe2 did not fire on known-broken fixtures")
        return 1
    if not controls["silent_on_good_state"]:
        print("FAILED:CNF-0077-probe2 good executable was not silent/green")
        return 1
    if not controls["no_artifact_classified_failure"]:
        print("FAILED:CNF-0077-probe2 no-artifact fixture counted executable")
        return 1
    if controls["mutant_no_artifact_as_executable_count"] == controls[
        "fixture_measured_executable_count"
    ]:
        print("FAILED:CNF-0077-probe2 mutant count equals measured (detector inert)")
        return 1
    if not S.every_row_complete(controls["rows"]):
        print("FAILED:CNF-0077-probe2 fixture row missing exit_code or artifact/error")
        return 1

    payload = {
        "probe": "probe2-detector-control",
        "unit_id": "CNF-0077",
        "pass": True,
        "fired_on_bad_state": True,
        "silent_on_good_state": True,
        "fixture_measured_executable_count": controls["fixture_measured_executable_count"],
        "fixture_catalog_claim": controls["fixture_catalog_claim"],
        "no_artifact_classified_failure": True,
        "placeholder_classified": controls["placeholder_classified"],
        "load_error_classified": controls["load_error_classified"],
        "catalog_omitted_still_enumerated": controls["catalog_omitted_still_enumerated"],
        "missing_catalog_file_not_invented": controls["missing_catalog_file_not_invented"],
        "reviewer": "CNF-0077-probe2-detector-control",
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"fx_measured={controls['fixture_measured_executable_count']} "
        f"fx_claim={controls['fixture_catalog_claim']} "
        f"no_artifact_failure={controls['no_artifact_classified_failure']} "
        f"omitted_visible={controls['catalog_omitted_still_enumerated']}"
    )
    print("SUCCESS:CNF-0077-probe2 detector control on known-broken fixtures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
