#!/usr/bin/env python3
"""Named probe 1: tag-matching precision/recall on the labelled fixture.

Requires precision and recall both >= 0.8, both-states cells present (TP and TN),
and a near-miss (taxidermy) that must not match tax-law.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from scenario import load_selector, read_json  # noqa: E402

UNIT = "IMP-0269"
MIN_P = 0.8
MIN_R = 0.8


def main() -> int:
    sel = load_selector()
    fixture = read_json("labelled-tags.json")
    rows = fixture["rows"]
    metrics = sel.tag_match_metrics(rows)
    cells = {r["row_id"]: r for r in metrics["rows"]}

    near = cells.get("tax-near-miss-taxidermy")
    alias = cells.get("tax-alias-taxation")
    empty_d = cells.get("empty-declared")

    ok = (
        metrics["n"] == len(rows)
        and metrics["precision"] >= MIN_P
        and metrics["recall"] >= MIN_R
        and metrics["tp"] > 0
        and metrics["tn"] > 0
        and metrics["fp"] == 0
        and metrics["fn"] == 0
        and near is not None
        and near["predicted"] is False
        and alias is not None
        and alias["predicted"] is True
        and empty_d is not None
        and empty_d["predicted"] is False
    )
    payload = {
        "probe": "probe1-tag-precision-recall",
        "unit_id": UNIT,
        "n": metrics["n"],
        "tp": metrics["tp"],
        "fp": metrics["fp"],
        "tn": metrics["tn"],
        "fn": metrics["fn"],
        "precision": metrics["precision"],
        "recall": metrics["recall"],
        "f1": metrics["f1"],
        "near_miss_rejected": bool(near and not near["predicted"]),
        "alias_matched": bool(alias and alias["predicted"]),
        "pass": ok,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"precision={metrics['precision']:.3f} recall={metrics['recall']:.3f} "
        f"tp={metrics['tp']} tn={metrics['tn']} fp={metrics['fp']} fn={metrics['fn']}"
    )
    if not ok:
        print(f"FAILED:{UNIT}-probe1 tag matcher below contract")
        return 1
    print(f"SUCCESS:{UNIT}-probe1 tag matching precision/recall")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
