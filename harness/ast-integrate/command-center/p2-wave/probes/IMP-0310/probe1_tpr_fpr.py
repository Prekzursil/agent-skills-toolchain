#!/usr/bin/env python3
"""IMP-0310 probe 1: TPR and FPR on the recorded corpus, reported separately.

Starts from the recorded traces (and the detector API), not from the author's
receipt summary. A single accuracy figure is a failure of this probe.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.council.stopping.deadlock import (  # noqa: E402
    CombinedAccuracyRefused,
    STALL_ROUNDS,
    build_recorded_corpus,
    combined_accuracy,
    evaluate,
    score_corpus,
    strip_scoring_fields,
    write_corpus,
)

CORPUS = HERE / "fixtures" / "recorded_corpus.json"
OUT = HERE / "probe1-tpr-fpr.raw.json"


def main() -> int:
    corpus = build_recorded_corpus()
    write_corpus(CORPUS)
    scored = score_corpus(corpus)
    rates = scored["rates"]
    rows = scored["rows"]

    refused = False
    refuse_msg = ""
    try:
        combined_accuracy(rates)
    except CombinedAccuracyRefused as exc:
        refused = True
        refuse_msg = str(exc)
    if not refused:
        print("FAILED:IMP-0310-probe1 combined_accuracy did not refuse")
        return 1

    n_slow = sum(1 for r in rows if r["label"] == "slow_converging")
    n_dead = sum(1 for r in rows if r["label"] == "deadlock")
    if n_slow != 20 or n_dead != 10:
        print(f"FAILED:IMP-0310-probe1 corpus size slow={n_slow} deadlock={n_dead}")
        return 1
    if rates["n_slow_labeled"] != 20 or rates["n_deadlock_labeled"] != 10:
        print("FAILED:IMP-0310-probe1 scored counts drifted from corpus")
        return 1

    tpr = rates["true_positive_rate"]
    fpr = rates["false_positive_rate"]
    if tpr is None or fpr is None:
        print("FAILED:IMP-0310-probe1 missing separate rates")
        return 1
    if abs(float(tpr) - 1.0) > 1e-12:
        misses = [r["id"] for r in rows if r["label"] == "deadlock" and not r["deadlock_predicted"]]
        print(f"FAILED:IMP-0310-probe1 TPR={tpr} misses={misses}")
        return 1
    if abs(float(fpr) - 0.0) > 1e-12:
        fps = [r["id"] for r in rows if r["label"] == "slow_converging" and r["deadlock_predicted"]]
        print(f"FAILED:IMP-0310-probe1 FPR={fpr} false_positives={fps}")
        return 1

    # Detector must ignore labels: flipping the label must not change the verdict.
    sample = corpus["constructed_deadlocks"][0]
    a = evaluate(sample)
    flipped = dict(strip_scoring_fields(sample))
    flipped["label"] = "slow_converging"
    b = evaluate(flipped)
    if a["deadlock"] != b["deadlock"] or a["classification"] != b["classification"]:
        print("FAILED:IMP-0310-probe1 detector consulted the label")
        return 1
    if "label" in strip_scoring_fields(sample):
        print("FAILED:IMP-0310-probe1 label leaked into detector input")
        return 1

    if any(k in rates for k in ("accuracy", "combined_accuracy", "f1", "f1_score")):
        print("FAILED:IMP-0310-probe1 combined figure present in rates")
        return 1
    if not rates.get("rates_reported_separately"):
        print("FAILED:IMP-0310-probe1 rates_reported_separately is not true")
        return 1

    slow_escalated = [r["id"] for r in rows if r["label"] == "slow_converging" and r["escalated"]]
    if slow_escalated:
        print(f"FAILED:IMP-0310-probe1 slow runs escalated: {slow_escalated}")
        return 1

    doc = {
        "probe": "probe1-tpr-fpr",
        "unit_id": "IMP-0310",
        "pass": True,
        "stall_rounds": STALL_ROUNDS,
        "true_positive_rate": tpr,
        "false_positive_rate": fpr,
        "true_positives": rates["true_positives"],
        "false_positives": rates["false_positives"],
        "true_negatives": rates["true_negatives"],
        "false_negatives": rates["false_negatives"],
        "n_deadlock_labeled": 10,
        "n_slow_labeled": 20,
        "combined_accuracy_refused": True,
        "combined_accuracy_refusal": refuse_msg,
        "label_ignored": True,
        "corpus_path": str(CORPUS.relative_to(REPO).as_posix()),
        "rows": rows,
    }
    OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(
        f"TPR={tpr} (tp={rates['true_positives']}/10) "
        f"FPR={fpr} (fp={rates['false_positives']}/20) "
        f"combined_accuracy=REFUSED stall_rounds={STALL_ROUNDS}"
    )
    print("SUCCESS:IMP-0310-probe1 TPR and FPR reported separately")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
