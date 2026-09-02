#!/usr/bin/env python3
"""Probe 2: detector control — planted unanchored certainty fires; good is silent.

This is the reviewer job: re-run the DETECTOR CONTROL on the known-broken
fixture and the known-good fixture. Re-reading a stored result does not count.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE / "lenses"))

from runner import artifact_field, known_present_control, run  # noqa: E402
import syn_0014  # noqa: E402

ART = REPO / "command-center/receipts/SYN-0027.json"
PLANT = HERE / "fixtures" / "planted-unanchored-certainty.md"
GOOD = HERE / "fixtures" / "good-anchored-certainty.md"


def fail(msg: str) -> int:
    print(f"FAILED:SYN-0027-probe2 {msg}")
    return 1


def main() -> int:
    # Live re-scan of the fixtures — not a read of a cached verdict.
    kpc = known_present_control()
    plant_rows = syn_0014.scan_path(PLANT)
    good_rows = syn_0014.scan_path(GOOD)
    bundle = run()
    payload = {
        "probe": "probe2-known-present",
        "unit_id": "SYN-0027",
        "fired": kpc["fired"],
        "silent_on_good": kpc["silent_on_good"],
        "both_states_discriminate": kpc["both_states_discriminate"],
        "plant_defect_ids": kpc["bad_finding_ids"],
        "good_defect_ids": kpc["good_finding_ids"],
        "plant_row_count": len(plant_rows),
        "good_row_count": len(good_rows),
        "dedup_rename_caught": bundle["dedup_planted_control"]["rename_caught"],
        "dedup_paraphrase_caught": bundle["dedup_planted_control"]["paraphrase_caught"],
        "dedup_parameter_fork_caught": bundle["dedup_planted_control"][
            "parameter_fork_caught"
        ],
        "dedup_distinct_not_collapsed": bundle["dedup_planted_control"][
            "distinct_not_collapsed"
        ],
        "overclaim_fired": bundle["overclaim_plant_control"]["fired"],
    }
    if not kpc["fired"]:
        return fail("planted unanchored 'almost certain' did not fire")
    if not kpc["silent_on_good"]:
        return fail(f"known-good anchored band fired {kpc['good_finding_ids']}")
    if not kpc["both_states_discriminate"]:
        return fail("both-states silent")
    if plant_rows == good_rows:
        return fail("planted and good scans produced identical rows")
    dpc = bundle["dedup_planted_control"]
    if not (
        dpc["rename_caught"]
        and dpc["paraphrase_caught"]
        and dpc["parameter_fork_caught"]
        and dpc["distinct_not_collapsed"]
    ):
        return fail(f"SYN-0017 planted mutants {dpc}")
    if not bundle["overclaim_plant_control"]["fired"]:
        return fail("'no unit fails' next to 12 of 103 did not fire")
    if not bundle["overclaim_plant_control"]["silent_on_scoped"]:
        return fail("scoped quantifier fired as overclaim")

    empty_src = [
        f
        for f in bundle["findings"]
        if f.get("lens") == "SYN-0022" and f.get("kind") == "undeclared-source-probe"
    ]
    rerun = [
        f
        for f in bundle["findings"]
        if f.get("lens") == "SYN-0022" and f.get("kind") == "same-probe-rerun"
    ]
    if not empty_src:
        return fail("empty source_probe was not classified VIOLATION")
    if not rerun:
        return fail("identical source/verifier fingerprints were not rejected")

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        k = artifact_field(doc, "known_present_control") or {}
        if not isinstance(k, dict) or k.get("fired") is not True or k.get("silent_on_good") is not True:
            return fail("artifact known_present_control did not record both-states")
        rev = doc.get("reviewer") or {}
        fired = rev.get("detector_control_fired")
        if fired is not True:
            fired = artifact_field(doc, "detector_control_fired")
        if fired is not True:
            return fail("reviewer did not record detector_control_fired")
        if rev.get("independent") is not True:
            return fail("reviewer.independent is not true")

    payload["pass"] = True
    print(json.dumps(payload, sort_keys=True))
    print("SUCCESS:SYN-0027-probe2 planted unanchored certainty fires; good is silent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
