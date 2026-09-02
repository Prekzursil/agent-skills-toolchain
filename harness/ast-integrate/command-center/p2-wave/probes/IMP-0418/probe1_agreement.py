#!/usr/bin/env python3
"""Probe 1: live 7-site agreement on the 200-artifact corpus (IMP-0418).

Re-runs the differential oracle. Does not trust the receipt's stored matrix.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

from predicate_oracle import MIN_BORDERLINE, run_oracle  # noqa: E402

RECEIPT = REPO / "command-center" / "receipts" / "IMP-0418.json"
SENTINEL = "SENTINEL:IMP-0418:PREDICATES-AGREE"


def main() -> int:
    result = run_oracle()
    payload = {
        "probe": "probe1-agreement",
        "unit_id": "IMP-0418",
        "corpus_size": result["corpus_size"],
        "call_sites": result["call_sites"],
        "borderline_count": result["borderline_count"],
        "complete_count": result["complete_count"],
        "incomplete_count": result["incomplete_count"],
        "pair_disagreement_sum": result["matrix"]["pair_disagreement_sum"],
        "any_disagreement": result["matrix"]["any_disagreement"],
        "oracle_too_easy": result["oracle_too_easy"],
        "agree": result["agree"],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if result["corpus_size"] != 200:
        print("FAILED:IMP-0418-probe1 corpus_size != 200")
        return 1
    if result["call_site_count"] != 7:
        print("FAILED:IMP-0418-probe1 call_site_count != 7")
        return 1
    if result["borderline_count"] < MIN_BORDERLINE:
        print("FAILED:IMP-0418-probe1 oracle too easy (borderline < 40)")
        return 1
    if result["matrix"]["any_disagreement"]:
        print("FAILED:IMP-0418-probe1 call sites disagree")
        return 1
    if not result["agree"]:
        print("FAILED:IMP-0418-probe1 oracle did not agree")
        return 1
    if RECEIPT.is_file():
        text = RECEIPT.read_text(encoding="utf-8")
        if SENTINEL not in text:
            print("FAILED:IMP-0418-probe1 receipt missing sentinel")
            return 1
        doc = json.loads(text)
        if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            print("FAILED:IMP-0418-probe1 receipt self-declares failure")
            return 1
        stored = (doc.get("oracle") or {}).get("pair_disagreement_sum")
        if stored != 0:
            print(f"FAILED:IMP-0418-probe1 receipt matrix sum {stored!r} != live 0")
            return 1
    print(
        f"corpus=200 sites=7 borderline={result['borderline_count']} "
        f"complete={result['complete_count']} disagreements=0"
    )
    print("SUCCESS:IMP-0418-probe1 seven call sites agree on 200 artifacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
