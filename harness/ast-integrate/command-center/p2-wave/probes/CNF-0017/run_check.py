#!/usr/bin/env python3
"""Run one named check under the current HOME/PATH. Exit 1 if failure observed."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import checks as C  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("FAILED:CNF-0017-run_check missing check id", file=sys.stderr)
        return 2
    cid = args[0]
    fn = C.CHECKS.get(cid)
    if fn is None:
        print(f"FAILED:CNF-0017-run_check unknown {cid}", file=sys.stderr)
        return 2
    observed = bool(fn())
    doc = {
        "id": cid,
        "failure_observed": observed,
        "home": str(C.home()),
        "outcome": "FAIL" if observed else "PASS",
    }
    print(json.dumps(doc, sort_keys=True))
    return 1 if observed else 0


if __name__ == "__main__":
    raise SystemExit(main())
