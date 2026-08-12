"""Detector control for the B1 citation detector -- BOTH states.

H1: `citations()` really finds names inside committed blobs.
H2: `citations()` is inert (bad pattern / wrong rev / rc swallowed) and its silence is
    meaningless.

A control that passes under BOTH hypotheses is not a control, so this asserts a COUNT on
each side, not merely that the function returned:

  FIRE : a name that is KNOWN-referenced by a tracked test must come back with >=1 citer,
         and the expected citer path must be among them.
  QUIET: a name that exists nowhere must come back with exactly 0 citers.
  SHAPE: the two must differ. If FIRE and QUIET both return 0 the instrument is dead.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _b1_cited_probes import citations  # noqa: E402

ROOT = "C:/Users/Prekzursil/source/ast-integrate"

KNOWN_REFERENCED = "_gen_schema_substrate.py"  # tracked test hardcodes this path
EXPECTED_CITER = "platform/lib/test_schema_resolver.py"
NONEXISTENT = "_zzz_control_no_such_probe_9f3a17.py"


def main():
    res = citations([KNOWN_REFERENCED, NONEXISTENT])
    fire = res[KNOWN_REFERENCED]
    quiet = res[NONEXISTENT]

    checks = {
        "fire_has_citers": len(fire) >= 1,
        "fire_includes_expected_citer": EXPECTED_CITER in fire,
        "quiet_is_zero": len(quiet) == 0,
        "states_distinguishable": len(fire) > len(quiet),
    }
    out = {
        "known_referenced": KNOWN_REFERENCED,
        "fire_citer_count": len(fire),
        "fire_citers": fire[:10],
        "nonexistent": NONEXISTENT,
        "quiet_citer_count": len(quiet),
        "checks": checks,
        "verdict": "PASS" if all(checks.values()) else "FAIL",
    }
    dst = os.path.join(ROOT, "command-center/slop-report/_b1_control.out.json")
    with open(dst, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
    print(json.dumps(out, indent=1))
    return 0 if out["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
