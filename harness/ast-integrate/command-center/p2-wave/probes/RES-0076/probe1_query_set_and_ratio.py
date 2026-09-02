#!/usr/bin/env python3
"""Probe 1: query set prints negative phrasings; ratio recomputed from snapshots.

Re-runs classify.py on the captured arXiv Atom files (not the artifact's
copied numbers) and requires the live ratio to match the record.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import classify as C  # noqa: E402
from check_record import SENTINEL, check_record  # noqa: E402

ART = REPO / "command-center/research/RES-0076.json"


def fail(msg: str) -> int:
    print(f"FAILED:RES-0076-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if SENTINEL not in ART.read_text(encoding="utf-8"):
        return fail("sentinel-absent")
    ok, why = check_record(doc)
    print(f"checker_ok={ok} {why}")
    if not ok:
        return fail(why)

    live = C.run_classification()
    rec_ratio = doc.get("retrieval_ratio") or {}
    for key in (
        "positive_total_results",
        "negative_total_results",
        "positive_over_negative",
        "mixed_query_positive_count",
        "mixed_query_negative_count",
    ):
        if rec_ratio.get(key) != live["retrieval_ratio"].get(key):
            return fail(f"ratio field {key} artifact={rec_ratio.get(key)} live={live['retrieval_ratio'].get(key)}")

    art_q = {q.get("id"): q for q in (doc.get("query_set") or []) if isinstance(q, dict)}
    live_neg = live["negative_phrasing_query_ids"]
    if len(live_neg) < 2:
        return fail("live query set lost negative phrasings")
    for qid in live_neg:
        row = art_q.get(qid)
        if not row:
            return fail(f"artifact dropped negative query {qid}")
        if not row.get("negative_phrasing"):
            return fail(f"artifact {qid} negative_phrasing false")
        if live["query_set"] and any(
            lq["id"] == qid and lq["total_results"] != row.get("total_results")
            for lq in live["query_set"]
        ):
            return fail(f"total_results drift on {qid}")

    if int(rec_ratio["positive_total_results"]) <= int(rec_ratio["negative_total_results"]):
        return fail("positive search did not retrieve more than the null search")

    print(
        f"neg_queries={live_neg} ratio={rec_ratio.get('positive_over_negative')} "
        f"mixed_pos={rec_ratio.get('mixed_query_positive_count')} "
        f"mixed_neg={rec_ratio.get('mixed_query_negative_count')}"
    )
    print("SUCCESS:RES-0076-probe1 query-set-and-ratio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
