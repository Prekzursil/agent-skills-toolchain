#!/usr/bin/env python3
"""IMP-0228 probe 2: zero dispatch during replay, counted, both-states."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))
sys.path.insert(0, str(REPO / "tools" / "agentspec" / "tests"))

from test_replay import (  # noqa: E402
    test_clock_free_modules,
    test_verdicts_roundtrip,
    test_zero_dispatch_both_states,
)


def main() -> int:
    zero = test_zero_dispatch_both_states()
    clock = test_clock_free_modules()
    verd = test_verdicts_roundtrip()
    print(json.dumps(zero, indent=2, sort_keys=True))
    print(json.dumps(clock, indent=2, sort_keys=True))
    print(json.dumps(verd, indent=2, sort_keys=True))
    ok = zero["pass"] and clock["pass"] and verd["pass"]
    if not ok:
        print("FAILED:IMP-0228-probe2 zero-dispatch")
        return 1
    print("SUCCESS:IMP-0228-probe2 zero dispatch counted; live path still dispatches")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
