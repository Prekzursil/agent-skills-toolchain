#!/usr/bin/env python3
"""Probe 1: every losing entry has classified rows XOR certified-nothing.

Both-states: deleting a certified-nothing loser or stripping A1 rows
without a certificate must fail the coverage checker.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import salvage as S  # noqa: E402

ART = S.REPO / S.OUT_REL


def main() -> int:
    if not ART.is_file():
        print("FAILED:ARC-0075-probe1 SALVAGE-REGISTER.json missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ARC-0075-probe1 self-declared {doc.get('state')}")
        return 1
    if S.UNIT_SENTINEL not in ART.read_text(encoding="utf-8"):
        print("FAILED:ARC-0075-probe1 sentinel absent")
        return 1
    ok, why = S.check_coverage(doc)
    print(f"coverage_ok={ok} {why}")
    if not ok:
        print("FAILED:ARC-0075-probe1 live coverage failed")
        return 1

    cert = S.domain(doc).get("certified_nothing") or []
    if not cert:
        print("FAILED:ARC-0075-probe1 no certified_nothing rows to mutate")
        return 1
    mutant_cert = copy.deepcopy(doc)
    dropped = S.domain(mutant_cert)["certified_nothing"].pop(0)
    mok, mwhy = S.check_coverage(mutant_cert)
    print(f"mutant_drop_cert entry={dropped.get('entry_id')} ok={mok} {mwhy}")
    if mok:
        print("FAILED:ARC-0075-probe1 coverage accepted a missing loser")
        return 1

    mutant_rows = copy.deepcopy(doc)
    drows = S.domain(mutant_rows)
    drows["salvage_rows"] = [
        r for r in drows.get("salvage_rows") or [] if r.get("losing_entry") != "A1"
    ]
    rok, rwhy = S.check_coverage(mutant_rows)
    print(f"mutant_drop_a1_rows ok={rok} {rwhy}")
    if rok:
        print("FAILED:ARC-0075-probe1 coverage accepted A1 with neither rows nor certificate")
        return 1

    rebuilt = S.build()
    ok2, why2 = S.check_coverage(rebuilt)
    print(f"rebuild_coverage_ok={ok2} {why2}")
    if not ok2:
        print("FAILED:ARC-0075-probe1 rebuild coverage failed")
        return 1
    print("SUCCESS:ARC-0075-probe1 coverage both-states certified-nothing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
