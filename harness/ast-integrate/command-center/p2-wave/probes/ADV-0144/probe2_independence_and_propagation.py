#!/usr/bin/env python3
"""Probe 2: corroboration independence + propagation.

Re-walks the raw fixture corpus (not the artifact's trace table). A
corroborating source that resolves to the same origin must NOT satisfy
the corroboration record. For the unlabeled incomplete trace, every
downstream consumer artifact must be named.
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
SAME_ID = "ADV0144-PLANT-SAME-ORIGIN"
EMPTY_ID = "ADV0144-PLANT-EMPTY"
UNRES_ID = "ADV0144-PLANT-UNRESOLVED"
OUT = HERE / "probe2-independence-and-propagation.raw.json"


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0144-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL_PREFIX not in text:
        return fail("sentinel absent")
    body = T.artifact_payload(doc)
    if body.get("same_origin_corroboration_rejected") is not True:
        return fail("artifact did not record same-origin rejection")
    if body.get("every_incomplete_trace_lists_downstream_consumers") is not True:
        return fail("artifact did not record downstream listing")

    corpus = T.load_corpus()
    stores = T.stores_from_corpus(corpus)
    same = T.evaluate_claim(T.claim_by_id(corpus, SAME_ID), stores)
    empty = T.evaluate_claim(T.claim_by_id(corpus, EMPTY_ID), stores)
    unres = T.evaluate_claim(T.claim_by_id(corpus, UNRES_ID), stores)

    same_rejected = (
        same["completeness"] == "INCOMPLETE"
        and "corroboration" in same["missing"]
        and same["four_record_verdict"]["label"] is True
        and same["four_record_verdict"]["audit_log"] is True
        and same["four_record_verdict"]["pre_output_review"] is True
        and same["corroboration_reason"] == "same-origin-corroboration-rejected"
    )
    empty_consumers = empty["downstream_consumers"]
    empty_paths = {c["artifact"] for c in empty_consumers}
    want_empty = {
        "command-center/p2-wave/probes/ADV-0144/fixtures/downstream-empty-consumer-a.json",
        "command-center/p2-wave/probes/ADV-0144/fixtures/downstream-empty-consumer-b.md",
    }
    propagation = want_empty <= empty_paths and len(empty_consumers) >= 2
    unres_incomplete = (
        unres["completeness"] == "INCOMPLETE"
        and unres["lineage_resolvable"] is False
        and unres["downstream_consumers"]
    )

    traces = {t["claim_id"]: t for t in body.get("traces") or []}
    art_same = traces.get(SAME_ID) or {}
    art_empty = traces.get(EMPTY_ID) or {}
    art_same_missing_corr = "corroboration" in (art_same.get("missing") or [])
    art_empty_paths = {
        c.get("artifact") for c in (art_empty.get("downstream_consumers") or [])
    }
    art_propagation = want_empty <= art_empty_paths

    incomplete = body.get("incomplete_traces") or []
    every_lists = all(
        isinstance(row, dict) and isinstance(row.get("downstream_consumers"), list)
        for row in incomplete
    )
    planted_incomplete_named = {EMPTY_ID, SAME_ID, UNRES_ID} <= {
        row.get("claim_id") for row in incomplete
    }

    # Independent re-walk must match the artifact table for planted ids.
    walk_match = (
        art_same.get("completeness") == same["completeness"]
        and art_empty.get("completeness") == empty["completeness"]
        and art_same_missing_corr
    )

    report = {
        "probe": "probe2-independence-and-propagation",
        "unit_id": "ADV-0144",
        "same_origin_rejected": same_rejected,
        "corroboration_reason": same["corroboration_reason"],
        "empty_consumer_count": len(empty_consumers),
        "empty_consumer_paths": sorted(empty_paths),
        "propagation_lists_both_consumers": propagation,
        "unresolved_is_incomplete_not_oos": unres_incomplete,
        "artifact_same_origin_missing_corroboration": art_same_missing_corr,
        "artifact_propagation": art_propagation,
        "every_incomplete_lists_downstream": every_lists,
        "planted_incomplete_named": planted_incomplete_named,
        "independent_walk_matches_artifact": walk_match,
        "no_live_onion_access": body.get("no_live_onion_access") is True,
    }
    OUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))

    if not same_rejected:
        return fail("same-origin corroboration was accepted")
    if not propagation:
        return fail(f"propagation missed consumers {empty_paths}")
    if not unres_incomplete:
        return fail("unresolved lineage was not INCOMPLETE")
    if not art_same_missing_corr:
        return fail("artifact accepted same-origin corroboration")
    if not art_propagation:
        return fail("artifact omitted downstream consumers")
    if not every_lists:
        return fail("an incomplete row omitted downstream_consumers")
    if not planted_incomplete_named:
        return fail("incomplete_traces missing planted ids")
    if not walk_match:
        return fail("independent raw-corpus walk disagrees with artifact table")
    print(
        "same_origin_rejected=True propagation=True unresolved_incomplete=True "
        "walk_match=True"
    )
    print(
        "SUCCESS:ADV-0144-probe2 same-origin corroboration rejected; "
        "incomplete traces list downstream consumers"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
