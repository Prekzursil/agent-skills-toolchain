#!/usr/bin/env python3
"""Probe 1: known-present control and planted omission.

A dissent that is paraphrased in the synthesis must match. Removing that
paragraph from a copy of the synthesis must report the dissent unmatched.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import audit as A  # noqa: E402

OUT = HERE / "probe1-known-present-omission.raw.json"


def main() -> int:
    dissents, full, omitted, _disposal = A.load_control()
    by_id = {d["id"]: d for d in dissents}
    present = by_id["D-PRESENT"]
    hatch = by_id["D-HATCH"]

    if A.substring_match(present["text"], full):
        print("FAILED:SYN-0016-probe1 D-PRESENT is a substring; fixture is not a paraphrase")
        return 1
    if A.substring_match(hatch["text"], full):
        print("FAILED:SYN-0016-probe1 D-HATCH is a substring; fixture is not a paraphrase")
        return 1

    cov_p, n_p, ov_p = A.coverage(present["text"], full)
    cov_h, n_h, ov_h = A.coverage(hatch["text"], full)
    hit_present = A.semantic_match(present["text"], full)
    hit_hatch = A.semantic_match(hatch["text"], full)
    miss_hatch = A.semantic_match(hatch["text"], omitted)
    still_present = A.semantic_match(present["text"], omitted)

    matched_full, unmatched_full = A.join(dissents, full, default_disposal=None)
    matched_omit, unmatched_omit = A.join(
        [present, hatch], omitted, default_disposal=None
    )
    unmatched_ids_omit = {r["id"] for r in unmatched_omit}
    matched_ids_full = {r["id"] for r in matched_full}

    snap = {
        "known_present": {
            "id": "D-PRESENT",
            "substring": False,
            "semantic": hit_present,
            "coverage": cov_p,
            "overlap_n": n_p,
            "overlap": sorted(ov_p),
        },
        "planted_omission": {
            "id": "D-HATCH",
            "substring_in_full": False,
            "semantic_in_full": hit_hatch,
            "semantic_in_omitted": miss_hatch,
            "coverage_full": cov_h,
            "overlap_n_full": n_h,
            "overlap_full": sorted(ov_h),
            "present_still_matches_omitted": still_present,
        },
        "matched_ids_full": sorted(matched_ids_full),
        "unmatched_ids_omitted_copy": sorted(unmatched_ids_omit),
    }
    OUT.write_text(json.dumps(snap, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(
        f"known_present semantic={hit_present} cov={cov_p:.3f} n={n_p} "
        f"hatch_full={hit_hatch} hatch_omitted={miss_hatch} "
        f"present_on_omitted={still_present}"
    )
    if not hit_present:
        print("FAILED:SYN-0016-probe1 known-present dissent did not match")
        return 1
    if not hit_hatch:
        print("FAILED:SYN-0016-probe1 hatch dissent did not match the full synthesis")
        return 1
    if miss_hatch:
        print("FAILED:SYN-0016-probe1 planted omission still matched")
        return 1
    if "D-HATCH" not in unmatched_ids_omit:
        print("FAILED:SYN-0016-probe1 omitted copy did not report D-HATCH unmatched")
        return 1
    if not still_present:
        print("FAILED:SYN-0016-probe1 known-present was lost when another paragraph was removed")
        return 1
    print("SUCCESS:SYN-0016-probe1 known-present and planted omission")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
