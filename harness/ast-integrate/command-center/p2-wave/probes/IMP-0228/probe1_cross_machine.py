#!/usr/bin/env python3
"""IMP-0228 probe 1: cross-machine replay reproduces plan bytes or names the gap."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))
sys.path.insert(0, str(REPO / "tools" / "agentspec" / "tests"))

from test_replay import (  # noqa: E402
    test_cross_machine_plan_bytes,
    test_host_leak_named_not_explained,
    test_missing_input_is_named,
)


def main() -> int:
    cross = test_cross_machine_plan_bytes()
    missing = test_missing_input_is_named()
    leak = test_host_leak_named_not_explained()
    print(json.dumps(cross, indent=2, sort_keys=True))
    print(json.dumps(missing, indent=2, sort_keys=True))
    print(json.dumps(leak, indent=2, sort_keys=True))
    ok = cross["pass"] and missing["pass"] and leak["pass"]
    if not ok:
        print("FAILED:IMP-0228-probe1 cross-machine replay")
        return 1
    print("SUCCESS:IMP-0228-probe1 cross-machine plan bytes or named missing input")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
