#!/usr/bin/env python3
"""Named probe 2: crashing input is minimised; seeds replay from the receipt.

Mechanically different from probe 1 (which scores triage cardinality).
This probe shrinks a padded 0xFF crash to a single token and asserts
every committed seed reconstitutes from its recorded recipe/sha256.
When the receipt exists, the same recipes and campaign seed replay
to the same triage fingerprints.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(HERE))

from scenario import (  # noqa: E402
    test_corpus_seeds_are_reproducible_from_the_receipt,
    test_crashing_input_is_minimised,
)


def main() -> int:
    mini = test_crashing_input_is_minimised()
    seeds = test_corpus_seeds_are_reproducible_from_the_receipt()
    ok = bool(mini["pass"] and seeds["pass"])
    payload = {
        "pass": ok,
        "probe": "probe2-minimise-and-replay",
        "unit_id": "TST-0117",
        "tests": [
            "test_crashing_input_is_minimised",
            "test_corpus_seeds_are_reproducible_from_the_receipt",
        ],
        "minimise": mini,
        "seeds": seeds,
    }
    print(json.dumps(payload, sort_keys=True))
    if not ok:
        print("FAILED:TST-0117-probe2 minimise or seed-replay")
        return 1
    print(
        "SUCCESS:TST-0117-probe2 minimised={0}b seed_count={1} "
        "receipt_present={2}".format(
            mini["minimised_nbytes"],
            seeds["seed_count"],
            seeds["receipt_present"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
