"""IMP-0153 probe 1 (source): hand-labelled 30-doc control set scores P/R as numbers.

Re-run: python command-center/p2-wave/probes/IMP-0153/probe1_control_scores.py
Exit 0 iff precision >= 0.8 and recall >= 0.8 on the frozen labels.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(W / "tools" / "workflow-foundry"))
import wf_usemention as UM  # noqa: E402

FIX = W / "tools" / "workflow-foundry" / "fixtures" / "IMP-0153"
RAW = Path(__file__).resolve().parent / "probe1-control-scores.raw.txt"

lines = []
scores = UM.score_control_set(FIX, FIX / "labels.json")
lines.append(json.dumps(scores, indent=1, sort_keys=True))

assert scores["documents"] == 30, "control set must be 30 docs"
assert scores["precision"] >= 0.8, "precision below 0.8"
assert scores["recall"] >= 0.8, "recall below 0.8"
lines.append("PASS: 30-doc control set scored precision={} recall={}".format(
    scores["precision"], scores["recall"]))

RAW.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
print("RESULT:" + json.dumps({
    "documents": scores["documents"],
    "precision": scores["precision"],
    "recall": scores["recall"],
    "tp": scores["true_positive"], "fp": scores["false_positive"],
    "fn": scores["false_negative"], "tn": scores["true_negative"],
}))
print("PASS")
