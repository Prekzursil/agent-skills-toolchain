#!/usr/bin/env python3
"""Probe 2: missing authorship, forged metadata vs ledger, rule (b) not inert.

Mechanically different from probe 1: this probe never consults the planted
self-confirmation fixture. It checks (1) omitted authorship is a violation,
(2) claimed confirmer contradicted by the tool-call ledger is a violation,
(3) an independent confirmer PASSES so the auditor is not a reject-all,
(4) a confirmer who only reviewed the implementation is rejected by rule (b)
while an authorship-only rule would accept them.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from audit import OUT_REL, SENTINEL, payload_of  # noqa: E402
from predicate import RULE_B, RULE_FORGED, RULE_MISSING, RULE_PASS, evaluate  # noqa: E402

ART = REPO / OUT_REL


def _load(name: str) -> dict:
    return json.loads((HERE / "fixtures" / name).read_text(encoding="utf-8"))


def main() -> int:
    missing = evaluate(_load("missing-authorship.json"))
    print(f"missing verdict={missing['independence_verdict']} rule={missing['deciding_rule']}")
    if missing["independence_verdict"] != "VIOLATION" or missing["deciding_rule"] != RULE_MISSING:
        print("FAILED:CNF-0124-probe2 missing authorship was not default-violation")
        return 1

    forged = evaluate(_load("forged-independent-label.json"))
    print(
        "forged verdict={v} rule={r} claimed={c} ledger_result={cr}".format(
            v=forged["independence_verdict"],
            r=forged["deciding_rule"],
            c=forged["confirmer_identity"],
            cr=forged["corroboration"]["result"],
        )
    )
    if forged["independence_verdict"] != "VIOLATION" or forged["deciding_rule"] != RULE_FORGED:
        print("FAILED:CNF-0124-probe2 forged metadata not caught by path/ledger")
        return 1
    authorship_only_forged = evaluate(_load("forged-independent-label.json"), enable_forged=False)
    if authorship_only_forged["independence_verdict"] != "PASS":
        print("FAILED:CNF-0124-probe2 forged case is not a metadata-only disguise")
        return 1

    independent = evaluate(_load("independent-ok.json"))
    print(
        f"independent verdict={independent['independence_verdict']} rule={independent['deciding_rule']}"
    )
    if independent["independence_verdict"] != "PASS" or independent["deciding_rule"] != RULE_PASS:
        print("FAILED:CNF-0124-probe2 independent control did not pass")
        return 1

    reviewer = _load("reviewer-overlap.json")
    full = evaluate(reviewer)
    auth_only = evaluate(reviewer, enable_b=False)
    print(
        "rule_b full={fv}/{fr} authorship_only={av}/{ar}".format(
            fv=full["independence_verdict"],
            fr=full["deciding_rule"],
            av=auth_only["independence_verdict"],
            ar=auth_only["deciding_rule"],
        )
    )
    if full["independence_verdict"] != "VIOLATION" or full["deciding_rule"] != RULE_B:
        print("FAILED:CNF-0124-probe2 rule-b did not reject implementation reviewer")
        return 1
    if auth_only["independence_verdict"] != "PASS":
        print("FAILED:CNF-0124-probe2 rule-b is inert (authorship-only also rejects)")
        return 1

    if not ART.is_file():
        print("FAILED:CNF-0124-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        print("FAILED:CNF-0124-probe2 sentinel absent")
        return 1
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0124-probe2 self-declared {doc.get('state')}")
        return 1
    payload = payload_of(doc)
    answers = payload.get("answers") or {}
    if answers.get("every_receipt_has_named_deciding_rule") is not True:
        print("FAILED:CNF-0124-probe2 unnamed deciding rule in artifact")
        return 1
    if answers.get("live_receipts_count") == 0 and not answers.get(
        "live_empty_reported_as_zero_of_zero"
    ):
        print("FAILED:CNF-0124-probe2 empty live corpus not reported as 0 of 0")
        return 1
    receipts = [r for r in (payload.get("receipts") or []) if isinstance(r, dict)]
    if not receipts:
        print("FAILED:CNF-0124-probe2 no receipts in artifact")
        return 1
    for row in receipts:
        if not row.get("deciding_rule") or row.get("independence_verdict") not in {
            "PASS",
            "VIOLATION",
        }:
            print(f"FAILED:CNF-0124-probe2 incomplete verdict {row.get('receipt_id')}")
            return 1
        if "confirmer_identity" not in row or "implementer_identity" not in row:
            print(f"FAILED:CNF-0124-probe2 missing identities {row.get('receipt_id')}")
            return 1
    print("SUCCESS:CNF-0124-probe2 missing-authorship forged-ledger rule-b independent-pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
