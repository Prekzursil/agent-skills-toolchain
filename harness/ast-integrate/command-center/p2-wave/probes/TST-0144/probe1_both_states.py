#!/usr/bin/env python3
"""Probe 1: both-states — complete artifact parses and caches; truncated fails condition 4 and is not cached."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from harness import run_strict_both_states  # noqa: E402


def main() -> int:
    result = run_strict_both_states()
    payload = {
        "ok": result["ok"],
        "probe": "probe1-both-states-complete-caches-truncated-not-cached",
        "tests": [
            {
                "id": "test_complete_artifact_parses_and_caches",
                "ok": bool(
                    result["complete"]["cached"]
                    and result["complete"]["consumer_holds"]
                    and result["complete"]["condition_4"]["condition_4"] == "SATISFIED"
                ),
            },
            {
                "id": "test_truncated_json_fails_condition_4_and_is_not_cached",
                "ok": bool(
                    result["truncated"]["failure"]
                    and result["truncated"]["cached"] is False
                    and result["truncated"]["consumer_holds"] is False
                    and result["truncated"]["condition_4"]["condition_4"] == "UNSATISFIED"
                    and 4 in result["truncated"]["condition_4"]["failing_condition_ids"]
                ),
            },
        ],
        "unit_id": "TST-0144",
        "complete": result["complete"],
        "truncated": result["truncated"],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not result["ok"]:
        print("FAILED:TST-0144-probe1 both-states truncated must fail condition 4 and leave cache empty")
        return 1
    fail = result["truncated"]["failure"] or {}
    print(
        "SUCCESS:TST-0144-probe1 complete caches; truncated byte_offset="
        f"{fail.get('byte_offset')} condition_4=UNSATISFIED cache_miss=True"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
