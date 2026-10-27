#!/usr/bin/env python3
"""IMP-0102 named test: repeat + shuffle invariance with a genuine score tie.

Standalone:  python3 -B tools/marketplace/tests/test_search_determinism.py
Importable:  provides QUERY, TIE_KEYS, _load() and
             test_repeat_and_shuffle_invariance() for the unit's named probes.

Signals (catalog evidence_requirement):
  1. the same query run 50 times returns one distinct result ordering;
  2. the index rebuilt from shuffled plugin order returns the identical
     ordering (16 seeded shuffles plus full reversal);
  and the ordering must include an actual score tie (bit-identical floats)
  broken by ascending stable key.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

TESTS = Path(__file__).resolve().parent
MARKETPLACE = TESTS.parent
TOOLS = MARKETPLACE.parent
REPO = TOOLS.parent
sys.path.insert(0, str(TOOLS))

from marketplace.search import POPULARITY_TERM, SearchIndex  # noqa: E402

QUERY = "quuxzorch"
TIE_KEYS = ("alpha-tie", "beta-tie")
CORPUS = MARKETPLACE / "fixtures" / "registry_corpus.json"
REPEATS = 50
SHUFFLE_SEEDS = 16


def _load():
    """The searchable corpus: tools/marketplace/fixtures/registry_corpus.json."""
    return json.loads(CORPUS.read_text(encoding="utf-8"))


def _ordering(index):
    return tuple(index.search(QUERY).keys())


def test_repeat_and_shuffle_invariance():
    data = _load()
    plugins = data["plugins"]
    base = SearchIndex.from_marketplace_data(data)
    order = _ordering(base)

    seen = {_ordering(SearchIndex.from_marketplace_data(data)) for _ in range(REPEATS)}
    if seen != {order}:
        raise AssertionError(
            "{0} repeats produced {1} distinct orderings".format(REPEATS, len(seen))
        )

    for seed in range(SHUFFLE_SEEDS):
        shuffled = list(plugins)
        random.Random(seed).shuffle(shuffled)
        got = _ordering(SearchIndex.from_marketplace_data({"plugins": shuffled}))
        if got != order:
            raise AssertionError(
                "shuffle seed={0} drifted: {1} != {2}".format(seed, got, order)
            )

    reversed_data = {"plugins": list(reversed(plugins))}
    if _ordering(SearchIndex.from_marketplace_data(reversed_data)) != order:
        raise AssertionError(
            "reversed insertion drifted: {0} != {1}".format(
                _ordering(SearchIndex.from_marketplace_data(reversed_data)), order
            )
        )

    hits = {h.stable_key: h for h in base.search(QUERY).hits}
    absent = [k for k in TIE_KEYS if k not in hits]
    if absent:
        raise AssertionError("corpus lost tie documents {0}".format(absent))
    if hits[TIE_KEYS[0]].score != hits[TIE_KEYS[1]].score:
        raise AssertionError(
            "tie is not a real score tie: {0!r} != {1!r}".format(
                hits[TIE_KEYS[0]].score, hits[TIE_KEYS[1]].score
            )
        )
    tie_order = [k for k in order if k in TIE_KEYS]
    if tie_order != list(TIE_KEYS):
        raise AssertionError("tie not broken by stable key: {0}".format(tie_order))
    if POPULARITY_TERM != 0.0:
        raise AssertionError("popularity term reappeared: {0!r}".format(POPULARITY_TERM))

    payload = {
        "probe": "test_repeat_and_shuffle_invariance",
        "unit_id": "IMP-0102",
        "pass": True,
        "query": QUERY,
        "ordering": list(order),
        "distinct_orderings_in_repeats": len(seen),
        "repeats": REPEATS,
        "shuffle_seeds": SHUFFLE_SEEDS,
        "tie_keys": list(TIE_KEYS),
        "tie_scores_equal": True,
        "popularity_term": POPULARITY_TERM,
    }
    print(json.dumps(payload, sort_keys=True))
    print("SUCCESS:IMP-0102 repeat and shuffle invariance")
    return True


if __name__ == "__main__":
    try:
        test_repeat_and_shuffle_invariance()
    except AssertionError as exc:
        print("FAILED:IMP-0102 {0}".format(exc))
        raise SystemExit(1)
    raise SystemExit(0)
