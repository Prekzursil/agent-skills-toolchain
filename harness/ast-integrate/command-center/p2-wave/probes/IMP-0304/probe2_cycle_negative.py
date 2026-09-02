#!/usr/bin/env python3
"""Named probe 2: cycle detection, independent recount, negative-control mutant."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from checks import run_probe2_body  # noqa: E402


def main() -> int:
    result = run_probe2_body()
    print(json.dumps(result, sort_keys=True))
    if result["pass"]:
        neg = result["checks"]["negative_control"]
        cyc = result["checks"]["cycle_detection"]
        print(
            f"cycle_fixtures={len(cyc.get('fixtures') or [])} "
            f"mutant_property={neg.get('property_assertion_on_mutant')} "
            f"mutant_after={neg.get('mutant_after')}"
        )
        print("SUCCESS:IMP-0304-probe2 cycle report and conservation-break negative control")
        return 0
    print("FAILED:IMP-0304-probe2")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
