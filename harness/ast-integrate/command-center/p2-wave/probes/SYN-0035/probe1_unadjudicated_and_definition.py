#!/usr/bin/env python3
"""Probe 1: unadjudicated excluded+counted; intervals from written definition."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from bands import WRITTEN_INTERVALS  # noqa: E402
from calibrate import (  # noqa: E402
    band_rows,
    is_adjudicated,
    run_calibration,
    tests_pass,
    unadjudicated_count,
)

UNIT = "SYN-0035"
ART = REPO / "command-center/synthesis/SYN-0035.calibration-report.json"
SENTINEL = (
    "SUCCESS:SYN-0035 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and every band row states n "
    "and the unadjudicated count is reported separately. Any other terminal "
    "state is FAILED:SYN-0035 <classification> with the diagnostic tail attached."
)


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("catalog sentinel absent")
    doc = json.loads(text)
    if doc.get("unit_id") != UNIT:
        return fail(f"unit_id={doc.get('unit_id')}")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")

    cal = run_calibration(REPO)
    if not tests_pass(cal):
        return fail("live calibration tests")
    tmap = {t["id"]: t for t in cal["tests"]}
    t1 = tmap["test_unadjudicated_claims_are_excluded_and_counted_not_imputed"]
    t3 = tmap["test_band_intervals_come_from_the_written_definition_not_from_the_data"]
    if t1["result"] != "PASS":
        return fail(f"unadjudicated test {t1}")
    if t3["result"] != "PASS":
        return fail(f"interval test {t3}")

    una = unadjudicated_count(cal["synthetic"])
    if int(doc.get("unadjudicated_count")) != una:
        return fail(
            f"unadjudicated_count artifact={doc.get('unadjudicated_count')} live={una}"
        )
    if una < 1:
        return fail("no unadjudicated rows to exclude")

    published = doc.get("bands") or []
    if len(published) != 5:
        return fail(f"band rows={len(published)} want=5")
    live_table = band_rows(cal["synthetic"])
    for row, want in zip(published, live_table):
        if row.get("n") != want["n"]:
            return fail(f"{want['band']} n artifact={row.get('n')} live={want['n']}")
        if row.get("unadjudicated_n") != want["unadjudicated_n"]:
            return fail(f"{want['band']} una mismatch")
        if list(row.get("nominal_interval")) != list(WRITTEN_INTERVALS[want["band"]]):
            return fail(f"{want['band']} interval not written definition")
        adj = [
            r
            for r in cal["synthetic"]
            if r["band"] == want["band"] and is_adjudicated(r["confirmer_verdict"])
        ]
        if row["n"] != len(adj):
            return fail(f"{want['band']} n includes unadjudicated")

    imputed = band_rows(cal["synthetic"], impute_unadjudicated_as="REFUTED")
    if imputed[0]["n"] == published[0]["n"] and imputed[0]["observed_hit_rate"] == published[0]["observed_hit_rate"]:
        return fail("REFUTED-imputation mutant did not change the table")

    likely = WRITTEN_INTERVALS["likely"]
    if tuple(likely) != (0.55, 0.80):
        return fail("likely is not 55-80")
    art_likely = next(r for r in published if r["band"] == "likely")
    if list(art_likely["nominal_interval"]) != [0.55, 0.80]:
        return fail("artifact likely interval is not 55-80")

    live_bands = doc.get("live_bands") or []
    live_ac = next(r for r in live_bands if r["band"] == "almost-certain")
    live_n = int(live_ac["n"])
    if live_n != len(
        [
            r
            for r in cal["live"]
            if r["band"] == "almost-certain" and is_adjudicated(r["confirmer_verdict"])
        ]
    ):
        return fail("live almost-certain n mismatch")

    if doc.get("likely_in_practice", {}).get("written_interval") != [0.55, 0.80]:
        return fail("likely_in_practice interval drifted")

    print(
        json.dumps(
            {
                "unadjudicated_count": una,
                "imputation_changes_rate": True,
                "likely_interval": [0.55, 0.80],
                "live_almost_certain_n": live_n,
                "live_almost_certain_rate": live_ac.get("observed_hit_rate"),
            },
            sort_keys=True,
        )
    )
    print(f"SUCCESS:{UNIT}-probe1 unadjudicated excluded; intervals written-not-fitted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
