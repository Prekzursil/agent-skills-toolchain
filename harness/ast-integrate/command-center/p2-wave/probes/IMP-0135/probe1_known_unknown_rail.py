#!/usr/bin/env python3
"""Probe 1: known rail PASS, unknown rail FAIL, no-rival-core AST walk green."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
ROUTING = REPO / "tools" / "agentspec" / "tests" / "test_workunit_routing.py"
RIVAL = REPO / "tools" / "agentrail" / "tests" / "test_no_rival_core.py"


def _run(path: Path) -> None:
    sys.path.insert(0, str(path.parent))
    ns = runpy.run_path(str(path), run_name="imp0135_probe1")
    code = ns["main"]()
    if code not in (0, None):
        raise SystemExit(f"FAILED:IMP-0135-probe1 {path.name} rc={code}")


def main() -> int:
    _run(ROUTING)
    _run(RIVAL)
    print("SUCCESS:IMP-0135-probe1 known/unknown rail and no-rival-core")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        print(f"FAILED:IMP-0135-probe1 {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
