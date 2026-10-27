#!/usr/bin/env python3
"""BLD-0028 probe2: census consistency verifier.

The receipt freezes a 466-document corpus and totals: 7145 semantic
zero-like results, 74 controlled, 7071 uncontrolled, 216 requeued producer
units, 105 use-vs-mention exclusions, 99 lane reports in scope. The corpus
itself lived on the producing substrate, but the ARITHMETIC and the
receipt's integrity are live-verifiable here, and the disposition engine is
re-derived on fresh fixtures (probe1) with a mutant that can go red.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from _shard6lib import ProbeFailure, check_receipt_core, require  # noqa: E402

UID = "BLD-0028"


def main() -> int:
    doc = check_receipt_core(UID)
    rep = doc["report"]
    obs = {o["name"]: o["measured"] for o in rep["observations"]}

    corpus = obs["corpus_documents_frozen"]
    zero_like = obs["semantic_zero_like_results"]
    controlled = obs["controlled_zero_results"]
    uncontrolled = obs["uncontrolled_zero_results"]
    requeued = obs["requeued_producing_units"]
    excluded = obs["use_vs_mention_exclusions"]
    lane = obs["lane_reports_in_scope"]

    require(controlled + uncontrolled == zero_like,
            f"arithmetic: {controlled}+{uncontrolled} != {zero_like}")
    require(requeued <= uncontrolled,
            f"requeued {requeued} exceeds uncontrolled {uncontrolled}")
    require(lane <= corpus, f"lane reports {lane} exceed corpus {corpus}")
    require(excluded <= corpus,
            f"exclusions {excluded} exceed corpus {corpus}")
    require(zero_like > corpus,
            "zero-like results should exceed document count (multi-claim docs)")

    # receipt integrity: every recorded test PASS, primary artifact present
    tests = doc.get("tests") or []
    require(tests and all(t.get("result") == "PASS" for t in tests),
            "a receipt test is not PASS")
    arts = doc.get("artifacts") or []
    primary = [a for a in arts if a.get("role") == "primary"]
    require(primary and primary[0].get("exists") is True,
            "primary artifact row absent")
    require(primary[0]["path"].endswith("receipts/BLD-0028.json"),
            "primary row path changed")

    # finding: disposition mismatches zero, direct verifier true
    require(obs["direct_verifier_passed"] is True, "direct verifier claim flipped")
    require(obs["harvester_reviewer_disposition_mismatches"] == 0,
            "disposition mismatches no longer zero")

    print(json.dumps({
        "probe": "probe2-census-consistency", "unit_id": UID,
        "arithmetic": f"{controlled}+{uncontrolled}={zero_like}",
        "requeued": requeued, "corpus": corpus, "lane_reports": lane,
        "tests_all_pass": len(tests), "pass": True,
    }, ensure_ascii=False))
    print(f"SUCCESS:{UID}-probe2 census arithmetic and receipt integrity hold")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ProbeFailure as exc:
        print(f"FAILED:{UID}-probe2 {exc}")
        raise SystemExit(1)
