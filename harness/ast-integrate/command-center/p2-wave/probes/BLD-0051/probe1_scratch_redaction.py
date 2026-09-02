#!/usr/bin/env python3
"""Probe 1: scratch plant across all writer classes and secret shapes.

Both-states: armed redactor strips the canary; unarmed writers still leak it
(proving the detector is not silent-pass).
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import constants as C  # noqa: E402
import scratch_writers as SW  # noqa: E402

ART = REPO / C.OUT_REL


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="bld0051-p1-") as tmp:
        report = SW.run_both_states(Path(tmp))
    printable = {
        "pass": report["pass"],
        "rows": report["rows"],
        "failed_count": len(report["failed"]),
        "writers": report["writers"],
        "shapes": report["shapes"],
        "canary_id": C.CANARY_ID,
    }
    print(json.dumps(printable, sort_keys=True))
    if not report["pass"]:
        print("FAILED:BLD-0051-probe1 scratch redaction")
        print(json.dumps(report["failed"], sort_keys=True)[:1500])
        return 1
    if len(report["writers"]) < 7:
        print("FAILED:BLD-0051-probe1 writer-class coverage")
        return 1
    needed = {"json-password", "camelCase-apiKey", "camelCase-passWord"}
    if not needed.issubset(set(report["shapes"])):
        print("FAILED:BLD-0051-probe1 shape coverage")
        return 1
    if not ART.is_file():
        print("FAILED:BLD-0051-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if C.CANARY in text:
        print("FAILED:BLD-0051-probe1 canary in live receipt")
        return 1
    if C.SENTINEL not in text:
        print("FAILED:BLD-0051-probe1 sentinel missing")
        return 1
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:BLD-0051-probe1 self-declared {doc.get('state')}")
        return 1
    print(
        f"armed_clean=True unarmed_leaks=True writers={len(report['writers'])} "
        f"shapes={len(report['shapes'])} rows={report['rows']}"
    )
    print("SUCCESS:BLD-0051-probe1 scratch redaction both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
