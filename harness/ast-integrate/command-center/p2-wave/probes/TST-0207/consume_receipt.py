#!/usr/bin/env python3
"""Downstream consumer for TST-0207: parse the catalog output_path receipt."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = REPO / "command-center" / "receipts" / "TST-0207.json"
SENTINEL = "SUCCESS:TST-0207"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def main() -> int:
    if not OUT.is_file() or OUT.stat().st_size <= 0:
        print("FAILED:TST-0207-consume receipt missing")
        return 1
    text = OUT.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:TST-0207-consume unparseable:{exc}")
        return 1
    if not isinstance(doc, dict):
        print("FAILED:TST-0207-consume not an object")
        return 1
    state = str(doc.get("state") or "").upper()
    if state in NOT_DELIVERING:
        print(f"FAILED:TST-0207-consume self-declared:{state}")
        return 1
    if SENTINEL not in text:
        print("FAILED:TST-0207-consume sentinel-absent")
        return 1
    if str(doc.get("unit_id") or "") != "TST-0207":
        print("FAILED:TST-0207-consume unit_id mismatch")
        return 1
    report = doc.get("report") or {}
    if str(report.get("kind") or "") != "security_report":
        print("FAILED:TST-0207-consume report.kind mismatch")
        return 1
    print(
        "consumer=command-center/p2-wave/probes/TST-0207/consume_receipt.py "
        f"path=command-center/receipts/TST-0207.json bytes={OUT.stat().st_size} "
        f"state={state} sentinel_present=true kind={report.get('kind')}"
    )
    print("SUCCESS:TST-0207-consume")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
