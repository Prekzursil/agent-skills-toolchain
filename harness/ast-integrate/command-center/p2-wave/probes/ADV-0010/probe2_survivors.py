#!/usr/bin/env python3
"""Probe 2: each fail-open survivor, mutated gate vs genuinely bad input, exit 0."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import emit as E  # noqa: E402
import harness as H  # noqa: E402

ART = REPO / E.OUT


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0010-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if int(doc.get("killed_count") or 0) < 1:
        return fail("killed_count<1")
    mids = list(doc.get("fail_open_survivors") or [])
    if not mids:
        # fall back to mutation rows
        mids = [
            row["id"]
            for row in doc.get("mutations") or []
            if row.get("status") == "SURVIVED" and row.get("fail_open")
        ]
    print(f"fail_open_survivors={mids}")
    if not mids:
        print("no fail-open survivors; killed-mutation control still holds")
        print("SUCCESS:ADV-0010-probe2 no fail-open survivor to demonstrate")
        return 0
    for mid in mids:
        demo = H.demonstrate_survivor(mid)
        print(
            f"survivor {demo['id']} exit_code={demo['exit_code']} "
            f"exits_zero_on_bad_input={demo['exits_zero_on_bad_input']} "
            f"detail={demo['detail']}"
        )
        if not demo["exits_zero_on_bad_input"]:
            return fail(f"{mid} did not exit 0 on bad input")
    print("SUCCESS:ADV-0010-probe2 survivor consequence (mutated gate exits 0 on bad input)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
