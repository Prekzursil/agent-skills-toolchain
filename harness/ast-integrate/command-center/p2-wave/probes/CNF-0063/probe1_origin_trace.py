#!/usr/bin/env python3
"""Probe 1: origin tracing, not URL counting.

Re-derives the circular-citation verdict from the fixture graph BEFORE reading
the artifact's conclusion fields, then checks the artifact matches. Mutating
the second source's cites list must flip the verdict (both-states). Naive
distinct-URL counting stays 'independent' in both states and is therefore inert.
"""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from audit import audit  # noqa: E402
from contract import validate_artifact  # noqa: E402
from lineage import (  # noqa: E402
    LABEL_INDEP,
    LABEL_SINGLE,
    SINGLE,
    classify_claim,
    naive_url_count_independent,
)

ART = REPO / "command-center/confirmation/CNF-0063-source-corroboration.json"
SCHEMA = REPO / "command-center/schema/citation-audit.schema.json"
SENTINEL_PREFIX = "SUCCESS:CNF-0063"


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0063-probe1 {msg}")
    return 1


def main() -> int:
    live = audit()
    by_live = {r["id"]: r for r in live["claims"]}
    circ = by_live["C-CIRCULAR-PLANT"]
    if circ["verdict"] != SINGLE or circ["label"] != LABEL_SINGLE:
        return fail(f"circular live verdict={circ['verdict']} label={circ['label']}")
    if circ["failure_class"] != "circular-citation":
        return fail(f"circular class={circ['failure_class']}")
    if not circ["lineage_trace"]["naive_url_count_would_call_independent"]:
        return fail("circular plant has <2 URLs so URL-count control cannot fire")

    mutant = deepcopy(next(c for c in live["claims"] if c["id"] == "C-CIRCULAR-PLANT"))
    # Rebuild from sources: drop the cite edge.
    raw_circ = deepcopy(circ)
    for src in raw_circ["sources"]:
        if src["id"] == "src-beta-news":
            src["cites"] = []
    flipped = classify_claim(
        {
            "id": raw_circ["id"],
            "claim": raw_circ["claim"],
            "planted": True,
            "sources": raw_circ["sources"],
        }
    )
    if flipped["verdict"] == SINGLE:
        return fail("dropping the cite edge did not make the pair independent")
    if flipped["label"] != LABEL_INDEP:
        return fail("independent mutant missing second-source label")
    naive_lit = naive_url_count_independent(circ["sources"])
    naive_dark = naive_url_count_independent(raw_circ["sources"])
    if not (naive_lit and naive_dark):
        return fail("URL-count matcher is not independent of the cite edge")
    if naive_lit and circ["verdict"] == SINGLE:
        pass  # origin tracer disagrees with URL counting — the required discrimination
    else:
        return fail("origin tracer did not disagree with URL counting on the circular plant")

    unlabeled = [r["id"] for r in live["claims"] if r["label"] not in {LABEL_INDEP, LABEL_SINGLE}]
    if unlabeled:
        return fail(f"unlabeled {unlabeled}")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if SENTINEL_PREFIX not in json.dumps(doc):
        return fail("sentinel absent")
    if not SCHEMA.is_file() or SCHEMA.stat().st_size <= 0:
        return fail("catalog output_schema missing")
    errors = validate_artifact(doc)
    if errors:
        return fail(f"schema-invalid {errors[0]}")
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")

    by_art = {r["id"]: r for r in doc["claims"]}
    if set(by_art) != set(by_live):
        return fail(f"id mismatch art={sorted(by_art)} live={sorted(by_live)}")
    for cid, row in by_live.items():
        art = by_art[cid]
        if art.get("verdict") != row["verdict"] or art.get("label") != row["label"]:
            return fail(f"{cid} artifact verdict drifted from live recompute")
        if art.get("label") not in {LABEL_INDEP, LABEL_SINGLE}:
            return fail(f"{cid} missing required label")

    art_circ = by_art["C-CIRCULAR-PLANT"]
    if art_circ["verdict"] != SINGLE or art_circ["label"] != LABEL_SINGLE:
        return fail("artifact did not label circular plant SINGLE-SOURCED")

    print(
        json.dumps(
            {
                "circular_origin_trace": SINGLE,
                "circular_naive_url_count": "INDEPENDENTLY-CORROBORATED",
                "cite_edge_mutant": flipped["verdict"],
                "url_count_lit_and_dark": True,
                "claims": len(live["claims"]),
                "single_sourced": live["single_sourced_count"],
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:CNF-0063-probe1 origin-trace circular-citation both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
