#!/usr/bin/env python3
"""Probe 1: planted self-confirmation must be flagged; live artifact records it.

Mechanically different from probe 2: this probe only asks whether the known
self-confirmation fixture (same agent as implementer and confirmer, P0 claim)
is a VIOLATION under rule (a). It does not inspect missing-authorship or ledger
forgery.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from audit import OUT_REL, SENTINEL, payload_of, validate_against_schema  # noqa: E402
from predicate import RULE_A, evaluate  # noqa: E402

ART = REPO / OUT_REL
PLANTED = HERE / "fixtures" / "planted-self-confirmation.json"


def main() -> int:
    receipt = json.loads(PLANTED.read_text(encoding="utf-8"))
    judged = evaluate(receipt)
    print(
        "isolated_planted verdict={v} rule={r} confirmer={c} implementer={i}".format(
            v=judged["independence_verdict"],
            r=judged["deciding_rule"],
            c=judged["confirmer_identity"],
            i=judged["implementer_identity"],
        )
    )
    if judged["independence_verdict"] != "VIOLATION" or judged["deciding_rule"] != RULE_A:
        print("FAILED:CNF-0124-probe1 planted fixture not flagged by rule-a")
        return 1
    if judged["confirmer_identity"] != judged["implementer_identity"]:
        print("FAILED:CNF-0124-probe1 planted fixture is not a self-confirmation")
        return 1
    if judged["claim_priority"] != "P0":
        print("FAILED:CNF-0124-probe1 planted fixture is not P0")
        return 1

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0124-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0124-probe1 self-declared {doc.get('state')}")
        return 1
    if SENTINEL not in text:
        print("FAILED:CNF-0124-probe1 sentinel absent")
        return 1
    errs = validate_against_schema(doc)
    if errs:
        print("FAILED:CNF-0124-probe1 schema", errs[0])
        return 1
    payload = payload_of(doc)
    answers = payload.get("answers") or {}
    if answers.get("planted_self_confirmation_flagged") is not True:
        print("FAILED:CNF-0124-probe1 artifact did not record planted flag")
        return 1
    planted_rows = [
        r
        for r in (payload.get("receipts") or [])
        if isinstance(r, dict) and r.get("receipt_id") == "planted-self-confirmation"
    ]
    if not planted_rows:
        print("FAILED:CNF-0124-probe1 planted receipt missing from artifact")
        return 1
    row = planted_rows[0]
    if row.get("independence_verdict") != "VIOLATION" or row.get("deciding_rule") != RULE_A:
        print("FAILED:CNF-0124-probe1 artifact planted row not VIOLATION/rule-a")
        return 1
    if answers.get("p0_or_p1_violation") is not True:
        print("FAILED:CNF-0124-probe1 P0 planted violation not counted as P0/P1")
        return 1
    print("SUCCESS:CNF-0124-probe1 planted self-confirmation flagged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
