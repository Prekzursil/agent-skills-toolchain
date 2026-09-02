#!/usr/bin/env python3
"""Probe 2: spec-enumerated source-class set difference + fingerprint recount.

Mechanically independent of probe 1:
  * class coverage reads catalog output_path presence (not the Jaccard clusterer)
  * floor recount uses exact fingerprint clustering (not Jaccard)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from candidates import (  # noqa: E402
    FAMILY_TARGETS,
    PLANT_DISTINCT_ID,
    PLANT_RENAME_ID,
    build_array,
    family_histogram,
    plant_distinct,
    plant_renamed_copy,
)
from coverage import class_coverage  # noqa: E402
from fork_discount import discount  # noqa: E402
from spec_classes import spec_ids  # noqa: E402

UNIT = "WFA-0160"
FLOOR = 160


def main() -> int:
    cov = class_coverage(REPO)
    spec = spec_ids()
    mechanical = sorted(set(spec) - set(cov["searched"]))
    inspect_rel = (
        "command-center/p2-wave/probes/WFA-0042/_inspect_source_out.json"
    )
    inspect_path = REPO / inspect_rel
    inspect = json.loads(inspect_path.read_text(encoding="utf-8"))
    inspect_hist = inspect.get("json_family_counts") or {}
    hist = family_histogram(build_array())
    hist_ok = hist == FAMILY_TARGETS == inspect_hist
    if not hist_ok:
        print(
            json.dumps(
                {
                    "probe": "probe2-class-difference",
                    "pass": False,
                    "error": "family histogram != WFA-0042 inspect json_family_counts",
                    "reconstructed": hist,
                    "family_targets": FAMILY_TARGETS,
                    "inspect": inspect_hist,
                },
                sort_keys=True,
            )
        )
        print(f"FAILED:{UNIT}-probe2 family-histogram mismatch")
        return 1
    if mechanical != cov["never_searched"]:
        print(
            json.dumps(
                {
                    "probe": "probe2-class-difference",
                    "pass": False,
                    "error": "never_searched != enumerated \\ searched",
                    "mechanical": mechanical,
                    "reported": cov["never_searched"],
                },
                sort_keys=True,
            )
        )
        print(f"FAILED:{UNIT}-probe2 set-difference mismatch")
        return 1

    base = build_array()
    base_fp = discount(base, method="fingerprint")
    planted = base + [plant_renamed_copy(), plant_distinct()]
    plant_fp = discount(planted, method="fingerprint")
    dropped = set(plant_fp["dropped_ids"])
    kept = set(plant_fp["kept_ids"])
    rename_dropped = PLANT_RENAME_ID in dropped
    distinct_survived = PLANT_DISTINCT_ID in kept
    floor_holds = base_fp["discounted_count"] >= FLOOR

    ok = (
        hist_ok
        and cov["enumerated_n"] == 16
        and cov["never_searched_n"] == len(mechanical)
        and set(cov["enumerated"]) == set(spec)
        and rename_dropped
        and distinct_survived
        and base_fp["raw_count"] == 284
        and int(inspect.get("json_n") or 0) == 284
        and floor_holds
        and "wf-saved-agentic-repair-reliability-copy" in dropped
    )
    payload = {
        "probe": "probe2-class-difference",
        "unit_id": UNIT,
        "method": "fingerprint+set-difference",
        "enumerated_n": cov["enumerated_n"],
        "searched_n": cov["searched_n"],
        "never_searched_n": cov["never_searched_n"],
        "never_searched": cov["never_searched"],
        "raw_count": base_fp["raw_count"],
        "discounted_count": base_fp["discounted_count"],
        "floor": FLOOR,
        "floor_holds": floor_holds,
        "family_histogram_matches_inspect": hist_ok,
        "rename_plant_dropped": rename_dropped,
        "distinct_plant_survived": distinct_survived,
        "pass": ok,
    }
    print(json.dumps(payload, sort_keys=True))
    if not ok:
        print(f"FAILED:{UNIT}-probe2 class-difference or fingerprint recount")
        return 1
    print(
        f"SUCCESS:{UNIT}-probe2 never_searched={cov['never_searched_n']}/16 "
        f"discounted={base_fp['discounted_count']} floor_holds={floor_holds}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
