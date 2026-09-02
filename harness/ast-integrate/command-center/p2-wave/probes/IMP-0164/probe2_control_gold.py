#!/usr/bin/env python3
"""Named probe 2 (IMP-0164): hand-labelled control reproduces exactly.

Gold is a frozen ordered list of (index, id, kind, fan_out_degree, gate,
inputs, outputs). Extraction must equal that list. A decoy gold with a
swapped kind must NOT match (comparison is not vacuously true). Fan-out
degree on the parallel stage is the number 2, not prose.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402
from foundry.stage_extract import projection  # noqa: E402


def main() -> int:
    # foundry is on sys.path via scenario import of tools/
    control = S.extract_control()
    got = projection(control)
    gold = S.CONTROL_GOLD
    print(f"extracted={json.dumps(got, sort_keys=True)}")
    print(f"gold={json.dumps(gold, sort_keys=True)}")

    if got != gold:
        print("FAILED:IMP-0164-probe2 extraction does not equal hand-labelled gold")
        return 1
    if not S.gold_matches(control):
        print("FAILED:IMP-0164-probe2 gold_matches returned false")
        return 1
    if control["span_coverage"] != 1.0 or not control["ok"]:
        print("FAILED:IMP-0164-probe2 gold match with unanchored stages")
        return 1

    parallel = got[1]
    if parallel["id"] != "implementers" or parallel["kind"] != "FAN_OUT":
        print("FAILED:IMP-0164-probe2 parallel stage identity")
        return 1
    if parallel["fan_out_degree"] != 2:
        print(
            f"FAILED:IMP-0164-probe2 fan_out_degree={parallel['fan_out_degree']!r} "
            "want int 2 (not prose)"
        )
        return 1
    if got[2]["gate"] != "diff.ok":
        print("FAILED:IMP-0164-probe2 critic gate not extracted")
        return 1

    decoy = copy.deepcopy(gold)
    decoy[1]["kind"] = "UNIT"
    if got == decoy:
        print("FAILED:IMP-0164-probe2 comparison cannot tell gold from a kind-swap")
        return 1
    if S.gold_matches({**control, "stages": []}):
        print("FAILED:IMP-0164-probe2 empty stage list matched gold")
        return 1

    empty = S.extract_all()["empty"]
    if projection(empty) is not None:
        print("FAILED:IMP-0164-probe2 honest-null projected a stage list")
        return 1

    doc = {
        "probe": "probe2-control-gold",
        "unit_id": "IMP-0164",
        "pass": True,
        "exact_match": True,
        "stage_count": len(got),
        "fan_out_degree": parallel["fan_out_degree"],
        "fan_out_degree_is_int": isinstance(parallel["fan_out_degree"], int),
        "decoy_kind_swap_rejected": got != decoy,
        "honest_null_projects_none": projection(empty) is None,
        "both_states": True,
        "fired_on_bad_state": got != decoy,
        "silent_on_good_state": got == gold,
    }
    (HERE / "probe2-control-gold.raw.json").write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print("SUCCESS:IMP-0164-probe2 hand-labelled control reproduces exactly")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
