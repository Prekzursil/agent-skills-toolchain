#!/usr/bin/env python3
"""Named probe 1: repeat + shuffle invariance, including a real score tie.

Signal 1: the same query run 50 times returns one distinct ordering.
Signal 2: the index rebuilt from shuffled plugin order returns that ordering.
Mechanically different from probe 2 (recall / empty-vs-error / skills[] / popularity).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "tools/marketplace/tests"))

import test_search_determinism as det  # noqa: E402
from marketplace.search import SearchIndex  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0102.json"


def _check_receipt() -> None:
    if not ART.is_file() or ART.stat().st_size < 200:
        raise SystemExit("FAILED:IMP-0102-probe1 receipt missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != "IMP-0102":
        raise SystemExit(f"FAILED:IMP-0102-probe1 unit_id {doc.get('unit_id')}")
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        raise SystemExit(f"FAILED:IMP-0102-probe1 self-declared:{doc.get('state')}")
    if "SUCCESS:IMP-0102" not in text:
        raise SystemExit("FAILED:IMP-0102-probe1 sentinel absent")


def main() -> int:
    _check_receipt()
    det.test_repeat_and_shuffle_invariance()
    data = det._load()
    index = SearchIndex.from_marketplace_data(data)
    result = index.search(det.QUERY)
    hits = {h.stable_key: h for h in result.hits}
    payload = {
        "probe": "probe1-repeat-shuffle",
        "unit_id": "IMP-0102",
        "pass": True,
        "query": det.QUERY,
        "ordering": list(result.keys()),
        "distinct_orderings_in_50": 1,
        "tie_keys": list(det.TIE_KEYS),
        "tie_scores_equal": hits[det.TIE_KEYS[0]].score == hits[det.TIE_KEYS[1]].score,
        "tie_broken_by_stable_key": [k for k in result.keys() if k in det.TIE_KEYS]
        == list(det.TIE_KEYS),
        "popularity_term": 0.0,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "tie equal={0} order={1}".format(
            payload["tie_scores_equal"], payload["ordering"]
        )
    )
    print("SUCCESS:IMP-0102-probe1 repeat and shuffle invariance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
