#!/usr/bin/env python3
"""Probe 1: both-states control — an in-scope write succeeds.

A unit scoped to tools/lib/ must actually create tools/lib/in-scope.txt.
The deny cases are not this probe's job; probe 2 owns the prefix-escape
regression. This probe still checks the in-scope filesystem landing so a
vacuous always-deny gate cannot pass.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from harness import run_all  # noqa: E402

ART = REPO / "command-center" / "receipts" / "TST-0224.json"


def main() -> int:
    summary = run_all()
    in_scope = next(c for c in summary["cases"] if c["id"] == "in-scope")
    payload = {
        "both_states": summary["both_states"],
        "fs_exists": in_scope["fs_after"]["exists"],
        "fs_sha256": in_scope["fs_after"]["sha256"],
        "pass": bool(summary["both_states"] and in_scope["pass"]),
        "probe": "probe1-both-states",
        "sut_allowed": in_scope["sut"]["allowed"],
        "sut_written": in_scope["sut"]["written"],
        "unit_id": "TST-0224",
    }
    print(json.dumps(payload, sort_keys=True))
    if not in_scope["sut"]["allowed"] or not in_scope["sut"]["written"]:
        print("FAILED:TST-0224-probe1 in-scope write was denied")
        return 1
    if not in_scope["fs_after"]["exists"]:
        print("FAILED:TST-0224-probe1 in-scope file missing after allow")
        return 1
    if not in_scope["pass"]:
        print("FAILED:TST-0224-probe1 in-scope case did not pass independent checks")
        return 1
    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        live = (doc.get("live_measurements") or {}).get("both_states") or {}
        if live.get("sut_allowed") is False:
            print("FAILED:TST-0224-probe1 artifact claims in-scope deny")
            return 1
    print("SUCCESS:TST-0224-probe1 in-scope write succeeded; file present on disk")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
