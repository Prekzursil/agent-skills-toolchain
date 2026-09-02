#!/usr/bin/env python3
"""Named probe 1: independently reproduce every B07 leak (not by reading the register)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from reproduce import circular_read_is_rejected, reproduce_all  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0158.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:CNF-0158-probe1 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    text = ART.read_text(encoding="utf-8")
    if doc.get("unit_id") != "CNF-0158" and doc.get("claim_id") != "CNF-0158":
        print("FAILED:CNF-0158-probe1 claim_id", doc.get("claim_id"))
        return 1
    if "SUCCESS:CNF-0158" not in text:
        print("FAILED:CNF-0158-probe1 sentinel absent")
        return 1
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNF-0158-probe1 self-declared", st)
        return 1
    if str(doc.get("verdict") or "").upper() == "BLOCKED":
        print("FAILED:CNF-0158-probe1 verdict BLOCKED")
        return 1

    result = reproduce_all()
    if not result["both_states"]:
        print("FAILED:CNF-0158-probe1 both-states: need >=1 REPRODUCED and >=1 ABSENT-AS-EXPECTED")
        print(json.dumps({"reproduced": result["reproduced_count"], "absent": result["absent_as_expected"]})[:2000])
        return 1
    if result["reproduced_count"] < 1:
        print("FAILED:CNF-0158-probe1 no leak reproduced")
        return 1
    if not circular_read_is_rejected(result):
        print("FAILED:CNF-0158-probe1 circular register-read was not rejected")
        return 1
    for row in result["rows"]:
        if row.get("evidence_is_register_read"):
            print("FAILED:CNF-0158-probe1 used register as evidence", row["id"])
            return 1
        if not row.get("evidence_is_observation"):
            print("FAILED:CNF-0158-probe1 missing observation", row["id"])
            return 1
        for vendor, vr in row["vendors"].items():
            if not vr.get("command"):
                print("FAILED:CNF-0158-probe1 missing command", row["id"], vendor)
                return 1
            if "observed_present=" not in vr.get("divergence", ""):
                print("FAILED:CNF-0158-probe1 missing divergence", row["id"], vendor)
                return 1

    receipt_leaks = {x["leak_id"]: x["verdict"] for x in (doc.get("leaks") or [])}
    live = {r["id"]: r["overall"] for r in result["rows"]}
    if receipt_leaks != live:
        print("FAILED:CNF-0158-probe1 receipt/live leak verdict mismatch")
        print(json.dumps({"receipt": receipt_leaks, "live": live}, indent=2)[:2000])
        return 1

    src = doc.get("source_probe") or {}
    if not str(src.get("fingerprint") or "") or len(str(src.get("command") or "")) < 8:
        print("FAILED:CNF-0158-probe1 empty source_probe")
        return 1

    summary = {
        "probe": "probe1-reproduce",
        "unit_id": "CNF-0158",
        "pass": True,
        "reproduced": result["reproduced_count"],
        "both_states": True,
        "circular_read_rejected": True,
        "leaks": live,
    }
    print(json.dumps(summary, sort_keys=True))
    print("SUCCESS:CNF-0158-probe1 independent leak reproduction")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
