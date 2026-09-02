#!/usr/bin/env python3
"""Probe 1: async window, reminder, timeout-to-proxy, both tallies.

Evidence (1): tally recomputation with and without the proxy, both live.
Also covers the catalog unit paths (window, reminder, timeout, proxy,
human-only).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

from scenario import evaluate_mixed, evaluate_unit_paths  # noqa: E402

ART = REPO / "command-center" / "receipts" / "IMP-0345.json"


def main() -> int:
    mixed = evaluate_mixed()
    units = evaluate_unit_paths()
    receipt_ok = True
    receipt_note = "receipt-not-required-for-module-paths"
    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        with_p = (doc.get("tally_recomputations") or {}).get("with_proxy") or {}
        without_p = (doc.get("tally_recomputations") or {}).get("without_proxy") or {}
        receipt_ok = (
            doc.get("unit_id") == "IMP-0345"
            and "SUCCESS:IMP-0345" in text
            and with_p.get("winner") == mixed["expected_with"]["winner"]
            and without_p.get("winner") == mixed["expected_without"]["winner"]
            and with_p.get("winner") != without_p.get("winner")
        )
        receipt_note = "receipt-records-both-tallies" if receipt_ok else "receipt-tally-mismatch"

    ok = mixed["pass"] and units["pass"] and receipt_ok
    payload = {
        "probe": "probe1-timeout-proxy-tally",
        "unit_id": "IMP-0345",
        "pass": ok,
        "mixed_pass": mixed["pass"],
        "unit_paths_pass": units["pass"],
        "unit_path_failed": units["failed"],
        "with_proxy": mixed["with_proxy"],
        "without_proxy": mixed["without_proxy"],
        "expected_with": mixed["expected_with"],
        "expected_without": mixed["expected_without"],
        "outcome_shifted": mixed["outcome_shifted"],
        "reminded_ids": mixed["reminded_ids"],
        "h3_origin": mixed["h3"]["origin"],
        "h3_marker": mixed["h3"]["proxy_origin_marker"],
        "receipt_ok": receipt_ok,
        "receipt_note": receipt_note,
    }
    print(json.dumps(payload, sort_keys=True))
    if not ok:
        print("FAILED:IMP-0345-probe1 timeout-proxy tally or unit paths")
        return 1
    print(
        "SUCCESS:IMP-0345-probe1 with_proxy="
        f"{mixed['with_proxy']['winner']} without_proxy="
        f"{mixed['without_proxy']['winner']} shifted="
        f"{mixed['outcome_shifted']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
