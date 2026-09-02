#!/usr/bin/env python3
"""Probe 2: independent Jaccard router + recount of stored TF-IDF selections.

Different metric and different text field than probe 1. Not a TF-IDF re-run.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import GOLD_PATH, OUTPUT_PATH, UNIT_ID, load_json  # noqa: E402
from inventory import write_inventory  # noqa: E402
from measure import evaluate  # noqa: E402


def _recount_stored(art: dict) -> list[dict]:
    out = []
    for block in art.get("per_task_primary") or []:
        rows = block.get("rows") or []
        correct = sum(1 for r in rows if r.get("correct") is True)
        n = len(rows)
        control_ok = all(r.get("selected") == r.get("gold_tool") for r in rows if r.get("control"))
        out.append(
            {
                "label": block.get("label"),
                "catalog_size": block.get("catalog_size"),
                "correct": correct,
                "n_tasks": n,
                "accuracy": (correct / n) if n else 0.0,
                "control_ok": control_ok,
            }
        )
    return out


def main() -> int:
    if not OUTPUT_PATH.is_file():
        print("FAILED:RES-0101-probe2 artifact missing")
        return 1
    art = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    if art.get("unit_id") != UNIT_ID or art.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:RES-0101-probe2 bad artifact state", art.get("state"), art.get("unit_id"))
        return 1

    gold = load_json(GOLD_PATH)
    inventory = write_inventory()
    jaccard = evaluate(gold, inventory, "jaccard-description")
    # Jaccard is the second metric, not the delivery harness. Control is required
    # on the TF-IDF stored rows (recounted below), not on this weaker router.

    recounted = _recount_stored(art)
    declared = art.get("accuracy_versus_catalog_size") or []
    if len(recounted) < 3 or len(declared) < 3:
        print("FAILED:RES-0101-probe2 need >=3 sizes")
        return 1
    for rec, dec in zip(recounted, declared):
        if rec["correct"] != dec.get("correct"):
            print("FAILED:RES-0101-probe2 recount mismatch", rec, dec)
            return 1
        if rec["catalog_size"] != dec.get("catalog_size"):
            print("FAILED:RES-0101-probe2 size mismatch", rec, dec)
            return 1
        if not rec["control_ok"]:
            print("FAILED:RES-0101-probe2 stored control failed", rec)
            return 1

    # Independence check: Jaccard must use a different router id and may differ numerically.
    if jaccard["router"] == (art.get("primary_router") or "tfidf-cosine-nameboost"):
        print("FAILED:RES-0101-probe2 router not independent")
        return 1
    j_sizes = [r["catalog_size"] for r in jaccard["accuracy_versus_catalog_size"]]
    j_acc = [r["accuracy"] for r in jaccard["accuracy_versus_catalog_size"]]
    t_acc = [r.get("accuracy") for r in declared]
    print(
        json.dumps(
            {
                "probe": "probe2-jaccard-and-recount",
                "unit_id": UNIT_ID,
                "jaccard_sizes": j_sizes,
                "jaccard_accuracy": j_acc,
                "tfidf_declared_accuracy": t_acc,
                "metrics_differ": j_acc != t_acc,
                "control_ok_every_size": True,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print(f"SUCCESS:RES-0101-probe2 jaccard sizes={j_sizes} acc={j_acc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
