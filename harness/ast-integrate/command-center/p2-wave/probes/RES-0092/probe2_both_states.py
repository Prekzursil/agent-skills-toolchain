#!/usr/bin/env python3
"""Probe 2: both-states control on the emitted checker.

Known-good fixture must stay silent under reverse permutation.
Known-broken fixture must fire under the same permutation.
Identity permutation must stay silent on both (false-positive control).
An independent frozenset/string rebinding must agree.
A checker silent in both states measures nothing.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from relation import (  # noqa: E402
    KNOWN_BROKEN,
    KNOWN_GOOD,
    both_states_run,
)
from threshold import VARIANCE_THRESHOLD  # noqa: E402


def main() -> int:
    row = both_states_run()
    print(
        json.dumps(
            {
                "known_good_id": KNOWN_GOOD["id"],
                "known_broken_id": KNOWN_BROKEN["id"],
                "threshold": VARIANCE_THRESHOLD,
                "fired_on_broken_reverse": row["fired_on_broken_reverse"],
                "silent_on_good_reverse": row["silent_on_good_reverse"],
                "identity_good_silent": row["identity_good_silent"],
                "identity_broken_silent": row["identity_broken_silent"],
                "independent_agrees": row["independent_agrees"],
                "silent_in_both_states": row["silent_in_both_states"],
                "scores_mixed": row["scores_mixed"],
                "positional_tuple_moves": row["positional_tuple_moves"],
                "good_reverse_distance": row["good"]["reversed"]["distance"],
                "broken_reverse_distance": row["broken"]["reversed"]["distance"],
                "good_reverse_source": row["good"]["reversed"]["source"],
                "good_reverse_followup": row["good"]["reversed"]["followup"],
                "broken_reverse_source": row["broken"]["reversed"]["source"],
                "broken_reverse_followup": row["broken"]["reversed"]["followup"],
            },
            sort_keys=True,
        )
    )
    ok = (
        row["fired_on_broken_reverse"]
        and row["silent_on_good_reverse"]
        and row["identity_good_silent"]
        and row["identity_broken_silent"]
        and row["independent_agrees"]
        and not row["silent_in_both_states"]
        and row["scores_mixed"]
        and row["positional_tuple_moves"]
    )
    print(
        f"fired_on_bad={row['fired_on_broken_reverse']} "
        f"silent_on_good={row['silent_on_good_reverse']} "
        f"identity_silent={row['identity_good_silent'] and row['identity_broken_silent']} "
        f"independent_agrees={row['independent_agrees']} "
        f"silent_in_both={row['silent_in_both_states']}"
    )
    if not ok:
        print("FAILED:RES-0092-probe2 both-states checker did not discriminate")
        return 1
    print(
        "SUCCESS:RES-0092-probe2 both-states fires only on known-broken "
        f"broken_distance={row['broken']['reversed']['distance']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
