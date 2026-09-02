#!/usr/bin/env python3
"""Probe 1: implement one MR, print the pre-stated threshold FIRST, then run it.

Control required by the catalog: state the acceptable-variance threshold
and how it was chosen, before running.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from threshold import (  # noqa: E402
    CHOSEN_BEFORE_RUN,
    DISTANCE_METRIC,
    RATIONALE,
    VARIANCE_THRESHOLD,
)
from relation import live_relation_run  # noqa: E402


def main() -> int:
    # Threshold is printed before any pipeline call in this process.
    print(f"pre_stated_variance_threshold={VARIANCE_THRESHOLD}")
    print(f"distance_metric={DISTANCE_METRIC}")
    print(f"threshold_stated_before_run={CHOSEN_BEFORE_RUN}")
    print(f"threshold_rationale={RATIONALE}")
    if not CHOSEN_BEFORE_RUN or VARIANCE_THRESHOLD != 0:
        print("FAILED:RES-0092-probe1 threshold was not the frozen pre-stated value")
        return 1
    run = live_relation_run()
    print(json.dumps(
        {
            "relation_id": run["relation_id"],
            "pipeline_step": run["pipeline_step"],
            "workflow_id": run["workflow_id"],
            "source_case_ids": run["source_case_ids"],
            "followup_case_ids": run["followup_case_ids"],
            "scores_mixed": run["scores_mixed"],
            "positional_tuple_moves": run["positional_tuple_moves"],
            "identity_distance": run["identity"]["distance"],
            "reversed_distance": run["reversed"]["distance"],
            "identity_violated": run["identity"]["violated"],
            "reversed_violated": run["reversed"]["violated"],
            "per_case": run["per_case"],
            "source_fingerprint": run["reversed"]["source"],
            "followup_fingerprint": run["reversed"]["followup"],
        },
        sort_keys=True,
    ))
    if not run["scores_mixed"] or not run["positional_tuple_moves"]:
        print("FAILED:RES-0092-probe1 fixture-unrepresentative: scores not mixed or palindromic")
        return 1
    if run["identity"]["violated"] or run["reversed"]["violated"]:
        print("FAILED:RES-0092-probe1 live pipeline violated MR-REORDER-UNORDERED-CASES")
        return 1
    if run["reversed"]["distance"] != 0:
        print("FAILED:RES-0092-probe1 reversed distance is not 0")
        return 1
    print(
        "SUCCESS:RES-0092-probe1 implemented MR-REORDER-UNORDERED-CASES "
        f"threshold={VARIANCE_THRESHOLD} reversed_distance={run['reversed']['distance']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
