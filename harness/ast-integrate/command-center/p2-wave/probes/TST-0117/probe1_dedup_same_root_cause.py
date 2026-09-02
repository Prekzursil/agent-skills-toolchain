#!/usr/bin/env python3
"""Named probe 1: two 0xFF inputs, one stack fingerprint, one triage entry.

Both-states control: the live stack-fingerprint collides the two inputs
into one entry; a payload-hash mutant splits them. A coverage-guided
campaign with a recorded seed must discover the planted 0xFF crash.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(HERE))

from scenario import test_two_inputs_with_one_root_cause_dedup_to_one_entry  # noqa: E402


def main() -> int:
    result = test_two_inputs_with_one_root_cause_dedup_to_one_entry()
    payload = {
        "pass": result["pass"],
        "probe": "probe1-dedup-same-root-cause",
        "unit_id": "TST-0117",
        "test": "test_two_inputs_with_one_root_cause_dedup_to_one_entry",
        "result": result,
    }
    print(json.dumps(payload, sort_keys=True))
    if not result["pass"]:
        print("FAILED:TST-0117-probe1 two same-root-cause crashes did not dedup")
        return 1
    print(
        "SUCCESS:TST-0117-probe1 live triage_count={0} mutant_count={1} "
        "campaign_triage={2}".format(
            result["live_triage_count"],
            result["mutant_payload_hash_triage_count"],
            result["campaign_triage_count"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
