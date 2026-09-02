#!/usr/bin/env python3
"""Probe 1: planted canary must fire; mention-only must not.

Mechanically the detector-control: a known-present synthetic credential in a
receipt, an event, and a packaged zip member. Use-versus-mention is the
negative control on the same run.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from scenario import run_canary, run_clean, run_mention  # noqa: E402
from secret_scrub_gate import report_contains_secret_body, synthetic_canary_value  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0458.json"
SENTINEL = "SENTINEL:IMP-0458:SECRET-SCRUB-REPORT-ONLY"


def main() -> int:
    canary = run_canary()
    mention = run_mention()
    clean = run_clean()
    print(
        json.dumps(
            {
                "probe": "probe1-canary-and-mention",
                "unit_id": "IMP-0458",
                "canary": canary,
                "mention": mention,
                "clean": clean,
            },
            indent=1,
            sort_keys=True,
        )
    )
    if not canary.get("fired"):
        print("FAILED:IMP-0458-probe1 canary did not fire on receipt+event+zip")
        return 1
    if not canary.get("fired_receipt"):
        print("FAILED:IMP-0458-probe1 receipt canary missed")
        return 1
    if not canary.get("fired_event"):
        print("FAILED:IMP-0458-probe1 event canary missed")
        return 1
    if not canary.get("fired_packaged"):
        print("FAILED:IMP-0458-probe1 packaged-artifact canary missed")
        return 1
    if canary.get("report_leaked_body"):
        print("FAILED:IMP-0458-probe1 scan report leaked canary body")
        return 1
    if not canary.get("hashes_unchanged"):
        print("FAILED:IMP-0458-probe1 canary tree mutated by the gate")
        return 1
    if mention.get("fired"):
        print("FAILED:IMP-0458-probe1 mention control fired")
        return 1
    if clean.get("fired"):
        print("FAILED:IMP-0458-probe1 clean fixture fired")
        return 1
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:IMP-0458-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:IMP-0458-probe1 receipt unparseable {exc}")
        return 1
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print(f"FAILED:IMP-0458-probe1 self-declared {doc.get('state')}")
        return 1
    if SENTINEL not in text:
        print("FAILED:IMP-0458-probe1 sentinel absent")
        return 1
    leaked = report_contains_secret_body(text, [synthetic_canary_value()])
    if leaked:
        print("FAILED:IMP-0458-probe1 receipt leaked canary body")
        return 1
    print("SUCCESS:IMP-0458-probe1 canary fire + mention silence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
