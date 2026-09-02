#!/usr/bin/env python3
"""Named probe 1: labelled-transcript precision and recall, reported separately.

The extractor sees only turns. Gold lives in a sibling file. Poison `_label`
fields on turns must not leak into predicted edges. A single accuracy figure
is not the contracted metric.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from evaluate import live_scores  # noqa: E402

RECEIPT = REPO / "command-center/receipts/IMP-0313.json"
MIN_PRECISION = 0.95
MIN_RECALL = 0.90


def main() -> int:
    live = live_scores()
    n_turns = live["n_turns"]
    precision = live["precision"]
    recall = live["recall"]
    if n_turns != 200:
        print(f"FAILED:IMP-0313-probe1 n_turns={n_turns} want=200")
        return 1
    if live["n_gold"] < 50:
        print(f"FAILED:IMP-0313-probe1 n_gold={live['n_gold']} want>=50")
        return 1
    if live["poison_edges"]:
        print(f"FAILED:IMP-0313-probe1 poison leaked {live['poison_edges']}")
        return 1
    if live["unresolved_turn_ids"]:
        print(
            "FAILED:IMP-0313-probe1 unresolved turn ids "
            f"{live['unresolved_turn_ids'][:8]}"
        )
        return 1
    if precision < MIN_PRECISION:
        print(
            f"FAILED:IMP-0313-probe1 precision={precision:.4f} "
            f"below {MIN_PRECISION} fps={live['false_positive_keys'][:8]}"
        )
        return 1
    if recall < MIN_RECALL:
        print(
            f"FAILED:IMP-0313-probe1 recall={recall:.4f} "
            f"below {MIN_RECALL} fns={live['false_negative_keys'][:8]}"
        )
        return 1
    if RECEIPT.is_file():
        doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
        text = json.dumps(doc)
        if "SUCCESS:IMP-0313" not in text:
            print("FAILED:IMP-0313-probe1 receipt missing sentinel")
            return 1
        claimed_p = doc.get("precision")
        claimed_r = doc.get("recall")
        if claimed_p is not None and abs(float(claimed_p) - precision) > 1e-9:
            print(
                f"FAILED:IMP-0313-probe1 receipt precision {claimed_p} "
                f"!= live {precision}"
            )
            return 1
        if claimed_r is not None and abs(float(claimed_r) - recall) > 1e-9:
            print(
                f"FAILED:IMP-0313-probe1 receipt recall {claimed_r} "
                f"!= live {recall}"
            )
            return 1
        if "accuracy" in doc and "precision" not in doc:
            print("FAILED:IMP-0313-probe1 receipt reports accuracy without precision")
            return 1

    summary = {
        "probe": "probe1-labelled-transcript-precision-recall",
        "unit_id": "IMP-0313",
        "n_turns": n_turns,
        "n_gold": live["n_gold"],
        "n_predicted": live["n_pred"],
        "precision": precision,
        "recall": recall,
        "true_positives": live["true_positives"],
        "false_positives": live["false_positives"],
        "false_negatives": live["false_negatives"],
        "poison_edges": live["poison_edges"],
        "unresolved_turn_ids": live["unresolved_turn_ids"],
        "pass": True,
        "metric_note": "precision and recall reported separately; no single accuracy",
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        f"precision={precision:.4f} recall={recall:.4f} "
        f"tp={live['true_positives']} fp={live['false_positives']} "
        f"fn={live['false_negatives']} n_turns={n_turns} n_gold={live['n_gold']}"
    )
    print("SUCCESS:IMP-0313-probe1 labelled-transcript precision/recall")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
