#!/usr/bin/env python3
"""Probe 1: live N=50 concurrent acquire. Raw counts, not a summary sentence."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import work_claim as wc  # noqa: E402

RECEIPT = REPO / "command-center" / "receipts" / "IMP-0409.json"
N = 50


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0409-p1-") as td:
        report = wc.run_concurrent_acquire(Path(td), "IMP-0409", n=N)
    granted = report["granted"]
    denied = report["denied"]
    missing_reason = [
        row
        for row in report["attempts"]
        if row["status"] == "DENIED" and not row.get("reason_code")
    ]
    receipt_ok = None
    if RECEIPT.is_file() and RECEIPT.stat().st_size > 0:
        text = RECEIPT.read_text(encoding="utf-8")
        doc = json.loads(text)
        receipt_ok = (
            str(doc.get("state") or "").upper()
            not in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
            and "SENTINEL:IMP-0409:CLAIMS-MUTUALLY-EXCLUSIVE" in text
            and int((doc.get("concurrency") or {}).get("granted") or -1) == 1
            and int((doc.get("concurrency") or {}).get("denied") or -1) == 49
            and len((doc.get("concurrency") or {}).get("attempts") or []) == 50
        )
    passed = (
        granted == 1
        and denied == N - 1
        and len(report["attempts"]) == N
        and not missing_reason
        and receipt_ok is not False
    )
    payload = {
        "probe": "probe1-concurrency-n50",
        "unit_id": "IMP-0409",
        "n": N,
        "granted": granted,
        "denied": denied,
        "reason_counts": report["reason_counts"],
        "attempts": report["attempts"],
        "denied_missing_reason_code": len(missing_reason),
        "receipt_present": RECEIPT.is_file(),
        "receipt_ok": receipt_ok,
        "pass": passed,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(
        f"RAW n={N} granted={granted} denied={denied} "
        f"reason_counts={json.dumps(report['reason_counts'], sort_keys=True)}"
    )
    if granted != 1 or denied != 49:
        print(f"FAILED:IMP-0409-probe1 expected granted=1 denied=49 got {granted}/{denied}")
        return 1
    if missing_reason:
        print("FAILED:IMP-0409-probe1 DENIED rows missing reason_code")
        return 1
    if receipt_ok is False:
        print("FAILED:IMP-0409-probe1 receipt missing sentinel or raw N=50 counts")
        return 1
    print("SUCCESS:IMP-0409-probe1 concurrency n=50 granted=1 denied=49 typed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
