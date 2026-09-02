#!/usr/bin/env python3
"""IMP-0219 probe 1: exit-0 + missing receipt => zero expansion + severed-stream.

Both-states: the healthy twin with a schema-valid receipt expands to 7 units.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))
sys.path.insert(0, str(REPO / "tools" / "agentspec" / "tests"))

from test_dynamic_fanout import (  # noqa: E402
    test_exit0_missing_receipt_zero_expansion_severed_stream,
)


def main() -> int:
    result = test_exit0_missing_receipt_zero_expansion_severed_stream()
    print(json.dumps(result, indent=2, sort_keys=True))
    both = {
        "bad_zero_and_severed": (
            result["bad"]["cardinality"] == 0
            and result["bad"]["reason"] == "severed-stream"
        ),
        "good_expands_to_7": result["good_cardinality"] == 7,
        "mutant_trusts_exit_0": result["mutant_trust_exit_code_cardinality"] == 1,
        "expand_calls_oracle": result["expand_calls_oracle"],
    }
    print(json.dumps({"both_states": both}, indent=2, sort_keys=True))
    if not result["pass"] or not all(both.values()):
        print("FAILED:IMP-0219-probe1 exit-0 missing receipt")
        return 1
    print("SUCCESS:IMP-0219-probe1 exit-0 missing receipt expands to zero + severed-stream")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
