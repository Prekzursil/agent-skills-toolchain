#!/usr/bin/env python3
"""Probe 1: planted opposite-verdict, count contradiction, false-positive guard.

Uses the on-disk B09/B10/B12 lane fixtures. Does not tally agents.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import detector as D  # noqa: E402

OUT = HERE / "probe1-planted.raw.json"


def main() -> int:
    planted = D.run_planted()
    ctrl = planted["controls"]
    OUT.write_text(json.dumps(planted, indent=2, default=str) + "\n", encoding="utf-8")

    checks = [
        ("opposite_verdict_detected", ctrl.get("opposite_verdict_detected")),
        ("count_contradiction_detected", ctrl.get("count_contradiction_detected")),
        ("similar_wording_different_files_not_flagged", ctrl.get("similar_wording_different_files_not_flagged")),
        ("tally_overruled_by_probe", ctrl.get("tally_overruled_by_probe")),
        ("self_count_classified_detector_failure", ctrl.get("self_count_classified_detector_failure")),
        ("self_verdict_classified_detector_failure", ctrl.get("self_verdict_classified_detector_failure")),
        ("release_mode_not_settled_by_majority", ctrl.get("release_mode_not_settled_by_majority")),
        ("controls_pass", ctrl.get("pass")),
        ("owner_source_present", planted.get("owner_source_present")),
        ("baseline_source_present", planted.get("baseline_source_present")),
    ]
    for name, ok in checks:
        print(f"{name}={ok}")
        if not ok:
            print(f"FAILED:BLD-0061-probe1 {name}")
            return 1

    rel_s = ctrl.get("release_mode_settlement") or {}
    ci_s = ctrl.get("ci_count_settlement") or {}
    if rel_s.get("status") != "RESOLVED-FROM-SOURCE" or rel_s.get("winner") != "B09-REL-MODE":
        print(f"FAILED:BLD-0061-probe1 release settlement {rel_s}")
        return 1
    if ci_s.get("status") != "RESOLVED-FROM-SOURCE" or ci_s.get("winner") != "B09-CI-COUNT":
        print(f"FAILED:BLD-0061-probe1 count settlement {ci_s}")
        return 1
    if ci_s.get("parsed_value") != 28:
        print(f"FAILED:BLD-0061-probe1 parsed_value {ci_s.get('parsed_value')}")
        return 1

    # Majority of agents would pick CONFIRMED (B09 + B12 tally of 5). Detector must not.
    n_contra = len(planted["contradictions"])
    n_fail = len(planted["detector_failures"])
    print(f"planted_claims={len(planted['claims'])} contradictions={n_contra} detector_failures={n_fail}")
    print("SUCCESS:BLD-0061-probe1 planted opposite-verdict count-contradiction fp-guard")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
