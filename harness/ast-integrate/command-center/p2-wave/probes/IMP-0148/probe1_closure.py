#!/usr/bin/env python3
"""IMP-0148 probe 1: AST-derived id set equals the documented set.

The catalog measured a 28-id baseline; Phase-7 extensions may grow the closed
set only when they are documented. Equality is the load-bearing check.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))

from agentspec.id_closure import check_closure  # noqa: E402

ORIGINAL_BASELINE = 28


def main() -> int:
    result = check_closure()
    print(json.dumps(result, sort_keys=True))
    if not result["equal"]:
        print(
            f"FAIL:IMP-0148-probe1 extra={result['extra']} missing={result['missing']}",
            file=sys.stderr,
        )
        return 1
    if (
        result["emitted_count"] < ORIGINAL_BASELINE
        or result["documented_count"] < ORIGINAL_BASELINE
    ):
        print(
            "FAIL:IMP-0148-probe1 expected at least the original 28-id baseline "
            f"got emitted={result['emitted_count']} documented={result['documented_count']}",
            file=sys.stderr,
        )
        return 1
    print(
        "SUCCESS:IMP-0148-probe1 "
        f"ast_derived={result['emitted_count']} documented={result['documented_count']} equal=True"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
