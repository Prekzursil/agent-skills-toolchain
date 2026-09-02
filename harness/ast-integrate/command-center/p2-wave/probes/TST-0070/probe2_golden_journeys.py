#!/usr/bin/env python3
"""Probe 2: three golden journeys against the installed artifact + dep census."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402


def main() -> int:
    result = H.run_golden_journeys()
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    if not result.get("pass"):
        print("FAILED:TST-0070-probe2 golden journeys or dep census not met")
        return 1
    journeys = result.get("journeys") or []
    names = [j.get("script") for j in journeys]
    sizes = [((j.get("postcondition") or {}).get("bytes")) for j in journeys]
    print(
        "journeys="
        + ",".join(str(n) for n in names)
        + " bytes="
        + ",".join(str(s) for s in sizes)
        + " corrupt_fired="
        + str((result.get("corruption_control") or {}).get("fired_on_corrupt"))
        + " missing_dep="
        + str((result.get("dep_census") or {}).get("answer"))
        + " jsonschema_load_bearing="
        + str((result.get("exec_policy_jsonschema") or {}).get("load_bearing"))
    )
    print(
        "SUCCESS:TST-0070-probe2 three golden journeys pass against installed "
        "artifact; jsonschema is in the repo and missing from the package"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
