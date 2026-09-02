#!/usr/bin/env python3
"""IMP-0138 probe 1: out-of-taxonomy reason fails validation (both-states)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))
sys.path.insert(0, str(REPO / "tools" / "agentspec" / "tests"))

from test_on_failure import (  # noqa: E402
    DEFAULT_ON_FAILURE,
    complete_policy,
    test_out_of_taxonomy_reason_fails_validation,
    validate_on_failure,
)


def main() -> int:
    result = test_out_of_taxonomy_reason_fails_validation()
    print(json.dumps(result, indent=2, sort_keys=True))

    good_errs = validate_on_failure(complete_policy())
    bad_policy = complete_policy()
    bad_policy["not-a-timeout"] = "abort"
    bad_errs = validate_on_failure(bad_policy)
    both = {
        "good_silent": len(good_errs) == 0,
        "bad_fires": any(e.id == "on-failure-unknown-reason" for e in bad_errs),
        "default_family_count": len(DEFAULT_ON_FAILURE),
    }
    print(json.dumps({"both_states": both}, indent=2, sort_keys=True))
    if not result["pass"] or not both["good_silent"] or not both["bad_fires"]:
        print("FAILED:IMP-0138-probe1 out-of-taxonomy")
        return 1
    print("SUCCESS:IMP-0138-probe1 out-of-taxonomy reason fails validation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
