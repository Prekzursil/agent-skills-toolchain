#!/usr/bin/env python3
"""IMP-0138 probe 2: one policy per family; set difference empty; not substring."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))
sys.path.insert(0, str(REPO / "tools" / "agentspec" / "tests"))

from test_on_failure import (  # noqa: E402
    test_family_coverage_set_difference,
    test_not_substring_branch,
)


def main() -> int:
    coverage = test_family_coverage_set_difference()
    substring = test_not_substring_branch()
    print(json.dumps(coverage, indent=2, sort_keys=True))
    print(json.dumps(substring, indent=2, sort_keys=True))
    if not coverage["pass"]:
        print("FAILED:IMP-0138-probe2 family coverage")
        return 1
    if coverage["unmapped"] or coverage["unknown"]:
        print("FAILED:IMP-0138-probe2 set difference not empty")
        return 1
    if not substring["pass"]:
        print("FAILED:IMP-0138-probe2 substring branch")
        return 1
    print("SUCCESS:IMP-0138-probe2 family coverage and not-substring")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
