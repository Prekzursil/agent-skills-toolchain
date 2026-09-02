#!/usr/bin/env python3
"""Probe 1: planted deep paraphrase is a near-duplicate; distinct is not."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import planted  # noqa: E402
import scan as SC  # noqa: E402
import similarity as S  # noqa: E402

ART = HERE.parents[3] / "command-center" / "receipts" / "CNF-0189.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:CNF-0189-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:CNF-0189" not in json.dumps(doc):
        print("FAILED:CNF-0189-probe1 sentinel absent")
        return 1

    recs = {r["id"]: r for r in planted.records()}
    seed = S.body_of(recs[planted.SEED_ID])
    control = SC.planted_control_pairs()
    cal = SC.calibrate(control)
    by_cls = {r["mutant_class"]: r for r in control}
    deep = by_cls["deep_paraphrase"]
    distinct = by_cls["distinct"]
    rename = by_cls["rename"]

    if not (SC.DEEP_JACCARD_MIN <= deep["jaccard"] <= SC.DEEP_JACCARD_MAX):
        print("FAILED:CNF-0189-probe1 deep Jaccard", deep["jaccard"])
        return 1
    if deep["cosine"] < cal["embedding_threshold"]:
        print("FAILED:CNF-0189-probe1 deep paraphrase missed by cosine")
        return 1
    if distinct["cosine"] >= cal["embedding_threshold"]:
        print("FAILED:CNF-0189-probe1 distinct scored as near-duplicate")
        return 1
    if rename["jaccard"] < 0.90:
        print("FAILED:CNF-0189-probe1 rename Jaccard", rename["jaccard"])
        return 1

    live = S.cosine_texts(seed, S.body_of(recs[planted.DEEP_ID]))
    if abs(live - deep["cosine"]) > 1e-6:
        print("FAILED:CNF-0189-probe1 live cosine mismatch", live, deep["cosine"])
        return 1

    print(
        json.dumps(
            {
                "probe": "probe1-planted",
                "deep_jaccard": deep["jaccard"],
                "deep_cosine": deep["cosine"],
                "distinct_cosine": distinct["cosine"],
                "embedding_threshold": cal["embedding_threshold"],
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:CNF-0189-probe1 planted deep paraphrase near-dup; distinct not")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
