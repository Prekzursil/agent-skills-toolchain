#!/usr/bin/env python3
"""Probe 2: order-control stability and independent matrix recomputation."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import corpus as C  # noqa: E402
import harness as H  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0156.json"


def main() -> int:
    if not ART.is_file():
        print("FAILED:CNF-0156-probe2 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:CNF-0156" not in json.dumps(doc):
        print("FAILED:CNF-0156-probe2 sentinel absent")
        return 1

    info = C.write_corpus()
    oracle = {row["id"]: row["ground_truth"] for row in info["oracle"]}
    order = H.run_order_control(info["dispatch"], oracle)

    by_vendor = {m["vendor"]: m for m in doc["confusion_matrices"]}
    for vendor in H.VENDORS:
        live = order[vendor]
        published = by_vendor[vendor]
        if live["counts"] != published["counts"]:
            print(
                "FAILED:CNF-0156-probe2 shuffled counts drifted",
                vendor,
                live["counts"],
                published["counts"],
            )
            return 1
        if live["false_pass_rate"] != published["false_pass_rate"]:
            print("FAILED:CNF-0156-probe2 false-pass unstable", vendor)
            return 1
        if live["false_alarm_rate"] != published["false_alarm_rate"]:
            print("FAILED:CNF-0156-probe2 false-alarm unstable", vendor)
            return 1
        if live["order"] == [i["id"] for i in info["dispatch"]]:
            print("FAILED:CNF-0156-probe2 shuffle no-op", vendor)
            return 1
        print(
            f"order-control vendor={vendor} seed={live['seed']} "
            f"counts={live['counts']} payload_sha={live['payload_sha256']}"
        )

    recomputed = {}
    for vendor in H.VENDORS:
        rows = [
            {"id": r["claim_id"], "verdict": r["verdict"]}
            for r in doc["raw_verdicts"]
            if r["vendor"] == vendor
        ]
        if len(rows) != doc["n"]:
            print("FAILED:CNF-0156-probe2 raw verdict count", vendor, len(rows))
            return 1
        matrix = H.confusion(rows, oracle)
        published = by_vendor[vendor]["counts"]
        if matrix["counts"] != published:
            print(
                "FAILED:CNF-0156-probe2 reviewer recompute mismatch",
                vendor,
                matrix["counts"],
                published,
            )
            return 1
        recomputed[vendor] = matrix["counts"]
        print(f"reviewer vendor={vendor} recomputed={matrix['counts']}")

    summary = {
        "pass": True,
        "probe": "probe2-order-stability",
        "unit_id": "CNF-0156",
        "recomputed_counts": recomputed,
        "order_seeds": {v: order[v]["seed"] for v in H.VENDORS},
    }
    print(json.dumps(summary, sort_keys=True))
    print("SUCCESS:CNF-0156-probe2 order-control and reviewer matrix recompute")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
