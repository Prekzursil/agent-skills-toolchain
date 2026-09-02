#!/usr/bin/env python3
"""Probe 1: detector control.

Plant a scratch claim with controversial-source lineage and none of the
four records. The live checker must report all four gaps. A mutant that
reports COMPLETE for an empty record set is inverted. A checker that
refuses a fully populated complete claim is also inverted (both states).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import trace as T  # noqa: E402

ART = REPO / "command-center/adversarial/ADV-0144-controversial-source-compliance.json"
SENTINEL_PREFIX = "SUCCESS:ADV-0144 emitted only when"
EMPTY_ID = "ADV0144-PLANT-EMPTY"
COMPLETE_ID = "ADV0144-PLANT-COMPLETE"
OUT = HERE / "probe1-detector.raw.json"


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0144-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "ADV-0144":
        return fail(f"unit_id {doc.get('unit_id')}")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    if SENTINEL_PREFIX not in ART.read_text(encoding="utf-8"):
        return fail("sentinel absent")

    corpus = T.load_corpus()
    stores = T.stores_from_corpus(corpus)
    empty = T.claim_by_id(corpus, EMPTY_ID)
    complete = T.claim_by_id(corpus, COMPLETE_ID)

    live_empty = T.evaluate_claim(empty, stores)
    live_complete = T.evaluate_claim(complete, stores)
    inverted = T.inverted_empty_is_complete(empty, stores)
    refused = T.refuse_everything(complete, stores)

    four = list(T.FOUR_RECORDS)
    empty_missing = live_empty["missing"]
    all_four = set(empty_missing) == set(four)
    inverted_fires = inverted.get("completeness") == "COMPLETE" and not inverted.get(
        "missing"
    )
    complete_ok = live_complete["completeness"] == "COMPLETE" and not live_complete[
        "missing"
    ]
    refuse_fires = refused.get("completeness") == "INCOMPLETE"

    body = T.artifact_payload(doc)
    traces = {t["claim_id"]: t for t in body.get("traces") or []}
    art_empty = traces.get(EMPTY_ID) or {}
    art_complete = traces.get(COMPLETE_ID) or {}
    art_records_all_four = set(art_empty.get("missing") or []) == set(four)
    art_complete_ok = art_complete.get("completeness") == "COMPLETE"

    report = {
        "probe": "probe1-detector",
        "unit_id": "ADV-0144",
        "empty_missing": empty_missing,
        "all_four_gaps": all_four,
        "inverted_reports_complete_on_empty": inverted_fires,
        "complete_is_complete": complete_ok,
        "refuse_everything_fires_on_complete": refuse_fires,
        "artifact_empty_all_four": art_records_all_four,
        "artifact_complete_ok": art_complete_ok,
        "live_empty_completeness": live_empty["completeness"],
        "live_complete_completeness": live_complete["completeness"],
    }
    OUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))

    if not all_four:
        return fail(f"empty claim missing {empty_missing}, want {four}")
    if not inverted_fires:
        return fail("inverted checker did not report complete on empty records")
    if not complete_ok:
        return fail("complete planted claim was not COMPLETE (refuse-everything bias)")
    if not refuse_fires:
        return fail("refuse-everything mutant silent on complete claim")
    if not art_records_all_four:
        return fail("artifact did not record all four gaps for empty plant")
    if not art_complete_ok:
        return fail("artifact did not record COMPLETE for populated plant")
    print(
        "all_four=True inverted_fires=True complete_ok=True refuse_fires=True"
    )
    print(
        "SUCCESS:ADV-0144-probe1 detector: empty records report all four gaps; "
        "inverted complete-on-empty fires"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
