#!/usr/bin/env python3
"""Named probe 1: ledger append, canonicalisation, both unique counts.

Signal 1 is a computed equality: 5 string-distinct ideas collapse to 3
mechanisms (3 circuit-breaker wordings + backoff + bulkhead). Signal 2
(different field): mutation APIs raise, JSONL tamper is refused, two
unknown paraphrases Jaccard-merge to one mechanism.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(HERE))

from scenario import evaluate_append_canonicalise  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0291.json"


def main() -> int:
    result = evaluate_append_canonicalise()
    print(json.dumps(result, indent=2, sort_keys=True))
    if not result["pass"]:
        print("FAILED:IMP-0291-probe1 ledger append/canonicalise")
        return 1
    counts = result["counts"]
    print(
        "string_distinct={0} mechanism_distinct={1} appended={2}".format(
            counts["string_distinct"],
            counts["mechanism_distinct"],
            counts["appended"],
        )
    )
    print(
        "SUCCESS:IMP-0291-probe1 ledger append and canonicalisation; "
        "counts reported side by side"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
