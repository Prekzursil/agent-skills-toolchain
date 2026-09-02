#!/usr/bin/env python3
"""IMP-0165 probe 1: invented role → UNKNOWN; known synonym maps (both-states).

Second signal on a different field: a nearest-neighbour mutant snaps
near-miss spellings onto critic; production exact-table lookup does not.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from scenario import both_states_synonym_vs_invented, no_silent_snap  # noqa: E402


def main() -> int:
    both = both_states_synonym_vs_invented()
    snap = no_silent_snap()
    payload = {
        "probe": "probe1-invented-vs-synonym",
        "unit_id": "IMP-0165",
        "both_states": both,
        "no_silent_snap": snap,
        "pass": bool(both["pass"] and snap["pass"]),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not payload["pass"]:
        print("FAILED:IMP-0165-probe1 invented/synonym or silent-snap")
        return 1
    print(
        "SUCCESS:IMP-0165-probe1 invented role is UNKNOWN; "
        "critic/red team/refuter map to critic; no nearest-neighbour snap"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
