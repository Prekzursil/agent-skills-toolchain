#!/usr/bin/env python3
"""Probe 2: mutation control (no atomic publish) plus leftover-temp inspection."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402


def main() -> int:
    mutant = H.run_mutation_control()
    leftovers = H.run_leftover_inspection()
    both_states = bool(mutant.get("detector_red")) and bool(leftovers.get("pass"))
    payload = {
        "probe": "probe2-mutation-temps",
        "unit_id": H.UNIT,
        "pass": both_states,
        "mutation": mutant,
        "leftover_inspection": leftovers,
        "both_states": {
            "atomic_publish_no_leftovers": leftovers.get("pass"),
            "inplace_partial_reads_appear": mutant.get("detector_red"),
        },
    }
    print(json.dumps(payload, sort_keys=True))
    if not mutant.get("detector_red"):
        print("FAILED:TST-0174-probe2 mutation control silent; no partial reads")
        return 1
    if not leftovers.get("pass"):
        print(
            "FAILED:TST-0174-probe2 leftover temps "
            f"{leftovers.get('leftover_tmps')}"
        )
        return 1
    print(
        "SUCCESS:TST-0174-probe2 "
        f"partial_reads={mutant.get('partial_reads')} "
        f"leftovers={leftovers.get('leftover_tmps')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
