#!/usr/bin/env python3
"""Probe 1: known-dead vs soft-error, and both-states intact vs dead."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from audit import run_control_suite  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0166.json"


def main() -> int:
    bundle = run_control_suite()
    tests = bundle["tests"]
    by_id = {r["id"]: r for r in bundle["citations"]}
    dead = by_id["ctrl-dead"]
    soft = by_id["ctrl-soft"]
    intact = by_id["ctrl-intact"]
    ok = (
        tests["known_dead"]["pass"] is True
        and tests["both_states"]["pass"] is True
        and tests["soft_vs_dead"]["pass"] is True
        and dead["classification"] == "dead"
        and dead["http_status"] == 404
        and soft["classification"] == "soft-error"
        and intact["classification"] == "intact"
        and intact["support_verdict"] == "SUPPORTS"
    )
    if ART.is_file() and ART.stat().st_size > 200:
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        if "SUCCESS:CNF-0166" not in text:
            print("FAILED:CNF-0166-probe1 sentinel absent from receipt")
            return 1
        if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            print("FAILED:CNF-0166-probe1 self-declared", doc.get("state"))
            return 1
        rt = doc.get("tests") or {}
        if rt.get("known_dead", {}).get("pass") is not True:
            print("FAILED:CNF-0166-probe1 receipt known_dead not PASS")
            return 1
        if rt.get("both_states", {}).get("pass") is not True:
            print("FAILED:CNF-0166-probe1 receipt both_states not PASS")
            return 1
    print(
        f"dead={dead['classification']}/{dead['http_status']} "
        f"soft={soft['classification']}/{soft['http_status']} "
        f"intact={intact['classification']} "
        f"ok={ok}"
    )
    if not ok:
        print("FAILED:CNF-0166-probe1 known-dead/both-states")
        return 1
    print("SUCCESS:CNF-0166-probe1 known-dead and both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
