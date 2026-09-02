#!/usr/bin/env python3
"""Probe 1: 100 generated briefs yield 0 conclusion fragments.

A vacuous detector (no distinctive needles on a receipt) fails this probe
even when leaks_found is 0, because that silence measures nothing.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0005-blind-brief-builder.json"
OUT = HERE / "probe1-clean-scan.raw.json"


def main() -> int:
    result = H.run_harness()
    clean = result["clean_scan"]
    payload = {
        "briefs": clean["briefs"],
        "leaks_found": clean["leaks_found"],
        "flagged_ids": clean["flagged_ids"],
        "vacuous_receipts": clean["vacuous_receipts"],
        "pass": False,
    }
    if clean["briefs"] < 100:
        print(f"FAILED:CNF-0005-probe1 briefs={clean['briefs']} want>=100")
        OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return 1
    if clean["vacuous_receipts"] != 0:
        print(f"FAILED:CNF-0005-probe1 vacuous detector on {clean['vacuous_receipts']} receipts")
        OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return 1
    if clean["leaks_found"] != 0:
        print(f"FAILED:CNF-0005-probe1 leaks_found={clean['leaks_found']} ids={clean['flagged_ids'][:8]}")
        OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return 1
    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        recorded = H.from_artifact(doc, "clean_scan").get("leaks_found")
        if recorded != 0:
            print(f"FAILED:CNF-0005-probe1 artifact clean_scan.leaks_found={recorded}")
            return 1
    payload["pass"] = True
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"briefs={clean['briefs']} leaks_found=0 vacuous=0 "
        f"live_receipts={result['corpus']['live_receipt_count']}"
    )
    print("SUCCESS:CNF-0005-probe1 100 clean briefs yield 0 conclusion fragments")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
