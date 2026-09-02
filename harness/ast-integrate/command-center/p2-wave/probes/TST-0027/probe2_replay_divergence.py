#!/usr/bin/env python3
"""Probe 2: same seed replays byte-identical verdicts; different seeds differ.

Negative control: an ignore-seed runner produces identical traces and is
caught as SeedIgnoredError. Re-running a stripped-seed receipt cannot replay.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from testinfra.test_seed_replay import (  # noqa: E402
    test_replay_from_seed_is_deterministic,
    test_two_different_seeds_produce_different_traces,
)


def main() -> int:
    replayed = test_replay_from_seed_is_deterministic()
    traces = test_two_different_seeds_produce_different_traces()
    ok = replayed["pass"] and traces["pass"]
    payload = {
        "probe": "probe2-replay-and-divergence",
        "unit_id": "TST-0027",
        "test_replay_from_seed_is_deterministic": replayed,
        "test_two_different_seeds_produce_different_traces": traces,
        "pass": ok,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not ok:
        print("FAILED:TST-0027-probe2 replay determinism or seed-use proof")
        return 1
    print(
        "SUCCESS:TST-0027-probe2 same-seed byte-identical verdicts; "
        "different seeds produce different traces"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
