#!/usr/bin/env python3
"""Probe 2: collapse supports that share an upstream source.

Raw support count and independent-source count must be different numbers
on the planted five-from-one control. Only independent_source_count may
be used for ranking. A collapser that always emits 1 is rejected by the
five-independent control.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from corpus import load_corpus  # noqa: E402
from graph import build, naive_raw_rank  # noqa: E402

ART = REPO / "command-center/audit/AUD-0071-support-edge-graph.json"
SENTINEL = (
    "SUCCESS:AUD-0071 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
FIVE_ONE = "CTL-FIVE-ONE-TARGET"
MIXED = "CTL-MIXED-TARGET"
FIVE_INDEP = "CTL-FIVE-INDEP-TARGET"


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0071-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file():
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")

    corpus = load_corpus()
    graph = build(corpus["claims"])
    tally = graph["tally"]
    naive = naive_raw_rank(tally)

    five = tally[FIVE_ONE]
    if five["raw_support_count"] != 5:
        return fail(f"five-from-one raw={five['raw_support_count']} want 5")
    if five["independent_source_count"] != 1:
        return fail(
            f"five-from-one independent={five['independent_source_count']} want 1"
        )
    if five["ranking_score"] != five["independent_source_count"]:
        return fail("ranking_score is not independent_source_count")
    if naive[FIVE_ONE] == five["independent_source_count"]:
        return fail("naive raw rank accidentally equals independent on five-from-one")
    if naive[FIVE_ONE] != 5:
        return fail("naive raw ranker did not see five repeats")

    mixed = tally[MIXED]
    if mixed["independent_source_count"] != 2 or mixed["raw_support_count"] != 2:
        return fail(
            f"mixed raw={mixed['raw_support_count']} indep={mixed['independent_source_count']}"
        )

    stay = tally[FIVE_INDEP]
    if stay["independent_source_count"] != 5:
        return fail(
            "five independent sources collapsed; detector is a constant-one"
        )

    if FIVE_ONE not in graph["raw_ne_independent"]:
        return fail("five-from-one not listed as raw!=independent")

    art_ctl = ((doc.get("control") or {}).get("five_records_one_upstream") or {})
    if art_ctl.get("independent_source_count") != 1:
        return fail("artifact control independent_source_count is not 1")
    if art_ctl.get("raw_support_count") != 5:
        return fail("artifact control raw_support_count is not 5")
    if art_ctl.get("ranking_score") != 1:
        return fail("artifact ranking_score used the raw count")
    if art_ctl.get("pass") is not True:
        return fail("artifact control.pass is not true")

    art_rows = {
        r["claim_id"]: r
        for r in (doc.get("per_claim") or [])
        if isinstance(r, dict) and r.get("claim_id")
    }
    for cid in (FIVE_ONE, MIXED, FIVE_INDEP):
        live = tally[cid]
        art = art_rows.get(cid) or {}
        if art.get("independent_source_count") != live["independent_source_count"]:
            return fail(f"artifact tally mismatch {cid}")
        if art.get("ranking_score") != live["ranking_score"]:
            return fail(f"artifact ranking_score mismatch {cid}")

    print(
        json.dumps(
            {
                "five_from_one": {
                    "raw_support_count": five["raw_support_count"],
                    "independent_source_count": five["independent_source_count"],
                    "ranking_score": five["ranking_score"],
                    "naive_raw_rank": naive[FIVE_ONE],
                },
                "mixed": {
                    "raw_support_count": mixed["raw_support_count"],
                    "independent_source_count": mixed["independent_source_count"],
                },
                "five_independent": {
                    "raw_support_count": stay["raw_support_count"],
                    "independent_source_count": stay["independent_source_count"],
                },
                "raw_ne_independent": graph["raw_ne_independent"],
                "ranking_uses": "independent_source_count",
            },
            indent=2,
            sort_keys=True,
        )
    )
    print("SUCCESS:AUD-0071-probe2 independent-source-collapse")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
