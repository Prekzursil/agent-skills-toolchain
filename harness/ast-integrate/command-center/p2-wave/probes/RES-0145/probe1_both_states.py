#!/usr/bin/env python3
"""Probe 1: both-states control — fire on all 10 cycles, silent on 10 independents.

A detector that fires on both classes measures nothing.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import corpus as C  # noqa: E402
import detector as D  # noqa: E402

UNIT = "RES-0145"
OUT = REPO / (
    "command-center/research/evidence-quality/"
    "RES-0145-circular-citation-detection.json"
)
SENTINEL = "SUCCESS:RES-0145"


def fail(msg: str) -> int:
    print(f"FAILED:RES-0145-probe1 {msg}")
    return 1


def main() -> int:
    if not OUT.is_file() or OUT.stat().st_size <= 0:
        return fail("artifact missing")
    text = OUT.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    if SENTINEL not in text:
        return fail("sentinel absent")

    planted = C.load_corpus()
    gold = C.gold_by_cluster()
    live_docs = C.documents_for_detector(planted)
    results = D.evaluate(live_docs)
    summary = D.summarize(results, gold)

    print(
        f"tp={summary['tp']} fn={summary['fn']} "
        f"tn={summary['tn']} fp={summary['fp']}"
    )
    print(
        f"detection_rate={summary['detection_rate']} "
        f"false_positive_rate={summary['false_positive_rate']}"
    )

    if summary["tp"] != 10 or summary["fn"] != 0:
        return fail(f"planted cycles not fully detected {summary}")
    if summary["fp"] != 0 or summary["tn"] != 10:
        return fail(f"independent clusters not fully silent {summary}")
    if not summary["both_states_pass"]:
        return fail("both-states control failed")

    art_rates = doc.get("rates") or {}
    if float(art_rates.get("detection_rate", -1)) != summary["detection_rate"]:
        return fail("artifact detection_rate drifted")
    if float(art_rates.get("false_positive_rate", -1)) != summary["false_positive_rate"]:
        return fail("artifact false_positive_rate drifted")

    both = doc.get("both_states_control") or {}
    if both.get("fires_on_all_planted_cycles") is not True:
        return fail("artifact both_states planted flag")
    if both.get("silent_on_all_independent_clusters") is not True:
        return fail("artifact both_states independent flag")

    # Detector must not need gold: stripping gold_kind if any still classifies.
    for row in live_docs:
        if "gold" in row or "gold_kind" in row:
            return fail("detector input still carries gold")

    print("both-states: 10/10 planted FIRE, 10/10 independent SILENT")
    print("SUCCESS:RES-0145-probe1 both-states control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
