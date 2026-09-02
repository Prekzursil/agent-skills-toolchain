#!/usr/bin/env python3
"""Named probe 1: reference client must pass every conformance fixture."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from marketplace.clients import ReferenceClient  # noqa: E402
from marketplace.conformance import run_client_against_cases  # noqa: E402


def main() -> int:
    result = run_client_against_cases(ReferenceClient())
    failed = [r["id"] for r in result["rows"] if not r["passed"]]
    out = {
        "probe": "probe1-reference-client",
        "unit_id": "IMP-0074",
        "client": "reference",
        "ok": result["ok"],
        "n": result["n"],
        "failed": failed,
        "passed": result["passed"],
    }
    print(json.dumps(out, sort_keys=True))
    if not result["passed"]:
        print("FAILED:IMP-0074-probe1 reference client did not pass conformance")
        return 1
    print(
        f"SUCCESS:IMP-0074-probe1 reference client {result['ok']}/{result['n']} fixtures"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
