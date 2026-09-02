#!/usr/bin/env python3
"""Subprocess substrate worker. Reads one JSON request on stdin, writes one row."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fusion_core as fc  # noqa: E402


def main() -> int:
    req = json.loads(sys.stdin.read())
    cases = {c["id"]: c for c in fc.matched_cases()}
    case = cases[req["case_id"]]
    row = fc.run_inprocess(req["workflow_id"], case, int(req["seed"]))
    row.pop("substrate", None)
    json.dump(row, sys.stdout, sort_keys=True, separators=(",", ":"))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
