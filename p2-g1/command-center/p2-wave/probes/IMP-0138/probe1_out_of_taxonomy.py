#!/usr/bin/env python3
"""IMP-0138 probe1: an on_failure reason outside the closed taxonomy fails
validation with on-failure-unknown-reason; the complete default map is silent
(both-states in one run)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))

from agentspec.on_failure import (  # noqa: E402
    DEFAULT_ON_FAILURE,
    VIOLATION_UNKNOWN,
    validate_on_failure,
)


def main() -> int:
    # BAD state: a parametrised-near-miss prose reason is NOT a taxonomy code.
    prose_key = "timeout: hung after 30s"
    bad = validate_on_failure({prose_key: "retry"})
    bad_fired = VIOLATION_UNKNOWN in bad

    # GOOD state: the complete default map is silent.
    good = validate_on_failure(dict(DEFAULT_ON_FAILURE))
    good_silent = not good

    # A genuine parametrised member also validates.
    genuine = validate_on_failure({"timeout-1800s": "retry", "rail-exit-137": "fanout-skip"})
    genuine_ok = not genuine

    result = {
        "unit_id": "IMP-0138",
        "probe": "probe1-out-of-taxonomy",
        "prose_key": prose_key,
        "bad_state_violations": bad,
        "bad_state_fires": bad_fired,
        "default_map_silent": good_silent,
        "parametrised_members_silent": genuine_ok,
        "pass": bad_fired and good_silent and genuine_ok,
    }
    print("RESULT:" + json.dumps(result))
    tail = ("SUCCESS:IMP-0138-probe1 out-of-taxonomy reason fails validation; "
            "default map silent (both-states)"
            if result["pass"] else
            "FAILED:IMP-0138-probe1 on-failure taxonomy contract broken")
    print(tail)
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
