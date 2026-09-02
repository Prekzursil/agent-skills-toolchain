#!/usr/bin/env python3
"""Probe 1: planted repeated-question recall and novel-question false-positive rate.

Control: every planted paraphrase of a settled question must retrieve that
council. A genuinely novel question must return no precedent. Recall and
false-positive rate are computed, not asserted.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.council.precedent import evaluate, load_corpus, load_eval_spec  # noqa: E402

CORPUS = HERE / "fixtures/corpus.json"
EVAL = HERE / "fixtures/eval.json"
MODULE = REPO / "tools/council/precedent.py"


def main() -> int:
    if not MODULE.is_file():
        print("FAILED:IMP-0258-probe1 tools/council/precedent.py missing")
        return 1
    if not CORPUS.is_file() or not EVAL.is_file():
        print("FAILED:IMP-0258-probe1 fixtures missing")
        return 1
    corpus = load_corpus(CORPUS)
    spec = load_eval_spec(EVAL)
    report = evaluate(spec, corpus)
    recall = report["recall"]["recall"]
    fpr = report["false_positives"]["false_positive_rate"]
    missed = [row for row in report["recall"]["rows"] if not row["ok"]]
    fps = [row for row in report["false_positives"]["rows"] if row["false_positive"]]
    payload = {
        "probe": "probe1-recall",
        "unit_id": "IMP-0258",
        "corpus_size": report["corpus_size"],
        "recall": recall,
        "recall_n": report["recall"]["n"],
        "recall_retrieved": report["recall"]["retrieved"],
        "false_positive_rate": fpr,
        "false_positive_n": report["false_positives"]["n"],
        "false_positives": report["false_positives"]["false_positives"],
        "missed": missed,
        "novel_hits": fps,
        "signals": ["token-jaccard", "char-3gram-dice"],
        "pass": recall == 1.0 and fpr == 0.0,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(
        f"recall={recall} n={payload['recall_n']} retrieved={payload['recall_retrieved']} "
        f"fpr={fpr} novel_n={payload['false_positive_n']}"
    )
    if recall != 1.0:
        print("FAILED:IMP-0258-probe1 planted repeated question not retrieved")
        return 1
    if fpr != 0.0:
        print("FAILED:IMP-0258-probe1 novel question returned a precedent")
        return 1
    print("SUCCESS:IMP-0258-probe1 planted recall and novel-question false-positive rate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
