#!/usr/bin/env python3
"""Probe 1: exercise author-untested CLI/hook surfaces for three fixed components."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from exercise import run  # noqa: E402

ART = HERE.parents[3] / "command-center/confirmation/CNF-0034-alternate-interface.json"


def main() -> int:
    doc = run()
    if not doc.get("pass"):
        print("FAILED:CNF-0034-probe1 alternate surfaces did not hold")
        print(json.dumps(doc, indent=2, default=str)[:4000])
        return 1
    freeze = doc["freeze"]
    stop = doc["stop"]
    if not freeze["library_cli_agree_clean"] or not freeze["library_cli_agree_dirty"]:
        print("FAILED:CNF-0034-probe1 freeze library/CLI disagreement")
        return 1
    if not freeze["mutant_cli_hides_tamper"]:
        print("FAILED:CNF-0034-probe1 mutant CLI control did not hide tamper")
        return 1
    if not stop["bad_cli_fired"] or stop["good_cli_fired"]:
        print("FAILED:CNF-0034-probe1 stop-hook CLI both-states failed")
        return 1
    if not stop["mutant_cli_silent_on_bad"]:
        print("FAILED:CNF-0034-probe1 mutant stop CLI did not stay silent")
        return 1
    if ART.is_file():
        body = ART.read_text(encoding="utf-8")
        if "SUCCESS:CNF-0034" not in body:
            print("FAILED:CNF-0034-probe1 artifact sentinel absent")
            return 1
    print(
        "freeze_cli_holds=True stop_cli_holds=True mutant_gap_detected=True "
        f"tamper_target={freeze['target']}"
    )
    print("SUCCESS:CNF-0034-probe1 untested CLI/hook surfaces hold")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
