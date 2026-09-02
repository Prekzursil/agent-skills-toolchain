#!/usr/bin/env python3
"""Probe 2: both-states shape-vs-substance control.

Repairing A6 citations must raise its rank. Padding A1 citations must drop
it to last. The naive URL-count matcher stays high on padding in both the
original A6 and the padded-A1 mutant (it cannot see substance).
"""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from corpus import APRIORI_BEST_TO_WORST, PADDED_ID, bodies, load_from_disk  # noqa: E402
from scorer import mutate_pad_gold, mutate_repair_padded, score_corpus  # noqa: E402


def _by_id(result: dict) -> dict:
    return {r["id"]: r for r in result["rows"]}


def main() -> int:
    arts = load_from_disk()
    base = score_corpus(arts, bodies())
    if not base["padded_is_lowest"]:
        print("FAILED:RES-0170-probe2 baseline padded is not lowest")
        return 1

    repaired_set = []
    for art in arts:
        if art["id"] == PADDED_ID:
            repaired_set.append(mutate_repair_padded(art))
        else:
            repaired_set.append(deepcopy(art))
    repaired = score_corpus(repaired_set, bodies())
    repaired_order = repaired["order_best_to_worst"]
    repaired_not_last = repaired_order[-1] != "A6-repaired"
    repaired_composite = _by_id(repaired)["A6-repaired"]["composite"]
    original_padded_composite = _by_id(base)[PADDED_ID]["composite"]
    repair_raises = repaired_composite > original_padded_composite + 0.2

    # Unique padded mutant: drop original A6 so last place is not a 0-0 id tie.
    padded_gold_set = []
    for art in arts:
        if art["id"] == "A1-gold":
            padded_gold_set.append(mutate_pad_gold(art))
        elif art["id"] == PADDED_ID:
            continue
        else:
            padded_gold_set.append(deepcopy(art))
    wrecked = score_corpus(padded_gold_set, bodies())
    wrecked_last = wrecked["order_best_to_worst"][-1] == "A1-padded-mutant"
    wrecked_row = _by_id(wrecked)["A1-padded-mutant"]
    naive_still_high = wrecked_row["naive_rank"] == 1

    # Independent second signal: naive matcher still ranks original padded first
    # while the substance metric ranks it last (already in probe 1). Probe 2
    # additionally requires the rank to FLIP under mutation.
    payload = {
        "probe": "probe2-shape-vs-substance",
        "unit_id": "RES-0170",
        "baseline_order": base["order_best_to_worst"],
        "baseline_padded_last": base["padded_is_lowest"],
        "baseline_naive_padded_first": base["naive_ranks_padded_first"],
        "repair": {
            "order": repaired_order,
            "a6_repaired_not_last": repaired_not_last,
            "composite_before": original_padded_composite,
            "composite_after": repaired_composite,
            "raises": repair_raises,
        },
        "pad_gold": {
            "order": wrecked["order_best_to_worst"],
            "a1_padded_is_last": wrecked_last,
            "naive_rank": wrecked_row["naive_rank"],
            "naive_still_high_on_padding": naive_still_high,
            "substance_rank": wrecked_row["rank"],
        },
        "both_states": repaired_not_last and wrecked_last and repair_raises,
        "pass": bool(
            base["padded_is_lowest"]
            and base["naive_ranks_padded_first"]
            and repaired_not_last
            and repair_raises
            and wrecked_last
            and naive_still_high
        ),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not payload["pass"]:
        print("FAILED:RES-0170-probe2 shape-vs-substance both-states")
        return 1
    print(
        "SUCCESS:RES-0170-probe2 repairing padding raises rank; padding gold "
        "drops it to last; naive URL-count stays high on padding"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
