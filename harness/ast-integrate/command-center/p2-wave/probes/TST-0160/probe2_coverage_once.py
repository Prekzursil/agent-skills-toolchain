#!/usr/bin/env python3
"""Probe 2: coverage denominator from the catalog; counting both runs fails.

Evidence (a): unique unit ids in the planted catalog (and the live catalog
occurrence of TST-0160, which must be one).

A mutant that treats each vendor run as its own covered unit inflates the
denominator and must be rejected. This probe does not re-classify provenance;
that is probe 1's job.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import replication as R  # noqa: E402

UID = "TST-0160"
RUNTIME = HERE / "runtime" / "probe2"


def fail(msg: str, payload: dict) -> int:
    print(json.dumps(payload, sort_keys=True))
    print(f"FAILED:{UID}-probe2 {msg}")
    return 1


def main() -> int:
    errors: list[str] = []
    catalog_ids = R.fixture_catalog_ids()
    observations = R.coverage_cohort()
    honest = R.coverage(catalog_ids, observations, count_each_run=False)
    mutant = R.coverage(catalog_ids, observations, count_each_run=True)
    honest_errs = R.reject_inflated_coverage(honest)
    mutant_errs = R.reject_inflated_coverage(mutant)
    live = R.live_catalog_once()
    cnf = R.cnf_vendor_frames()

    R.write_ledger(
        RUNTIME / "cohort.json",
        observations,
        extra={
            "honest": honest,
            "mutant": mutant,
            "catalog_ids": catalog_ids,
        },
    )

    if len(set(catalog_ids)) != 5:
        errors.append(f"fixture-catalog-unique:{len(set(catalog_ids))}")
    if honest["denominator"] != 5:
        errors.append(f"honest-denominator:{honest['denominator']}")
    if honest["catalog_unique_ids"] != 5:
        errors.append("honest-catalog-unique")
    if honest["observation_count"] != 6:
        errors.append(f"observation-count:{honest['observation_count']}")
    if honest["covered_logical_units"] != 5:
        errors.append("honest-covered-logical")
    if honest["inflated"] is True:
        errors.append("honest-marked-inflated")
    if honest_errs:
        errors.append(f"honest-rejected:{honest_errs}")

    if mutant["denominator"] != 6:
        errors.append(f"mutant-denominator:{mutant['denominator']}")
    if mutant["inflated"] is not True:
        errors.append("mutant-not-inflated")
    if not mutant_errs:
        errors.append("mutant-was-not-rejected")
    if mutant["denominator"] == honest["denominator"]:
        errors.append("mutant-did-not-change-denominator")

    if live["present"] is not True:
        errors.append("live-catalog-absent")
    elif live["uid_occurrences"] != 1:
        errors.append(f"live-catalog-occurrences:{live['uid_occurrences']}")
    if live["unique_ids"] < 1:
        errors.append("live-catalog-empty")

    payload = {
        "cnf_vendor_frames": cnf,
        "errors": errors,
        "honest": honest,
        "live_catalog": live,
        "mutant": mutant,
        "mutant_rejected": bool(mutant_errs),
        "negative_control_fired": bool(mutant_errs) and mutant["inflated"] is True,
        "pass": not errors,
        "probe": "probe2-coverage-once",
        "unit_id": UID,
    }
    if errors:
        return fail(",".join(errors), payload)
    print(json.dumps(payload, sort_keys=True))
    print(
        f"honest_denom={honest['denominator']} mutant_denom={mutant['denominator']} "
        f"obs={honest['observation_count']} live_once={live['uid_occurrences']} "
        f"mutant_rejected={bool(mutant_errs)}"
    )
    print("SUCCESS:TST-0160-probe2 coverage-once negative-control fired")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
