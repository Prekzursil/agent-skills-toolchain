#!/usr/bin/env formula2
"""TST-0282 probe 2: adversarial padding + both-states threshold reach.

  - adversarial: the padded-volume case carries ~1590+ words but covers only
    one subquestion with no evidence citation -> score must stay BELOW 0.90.
  - both-states: a genuinely complete case must REACH 1.0 (the threshold is
    reachable, the gate is not a permanent block), and extra undeclared
    padding on top of a complete case must NOT move the score (extra volume
    is ignored by the min-coverage formula).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from gold import BODY_LONG, BODY_PAD, build  # gold.py adjacent  # noqa: E402

sys.path.insert(0, str(REPO / "tools"))
from council.completeness import score_output  # noqa: E402

THRESHOLD = 0.90


def main() -> int:
    checks: dict[str, bool] = {}
    o = {
        "subquestions": [{"id": "sq0"}, {"id": "sq1"}],
        "required_categories": ["cat0", "cat1"],
        "evidence_classes": ["ev0"],
    }

    def answers_full():
        return [
            {"subquestion_id": "sq0", "body": BODY_LONG, "categories": ["cat0", "cat1"]},
            {"subquestion_id": "sq1", "body": BODY_LONG, "categories": ["cat0"]},
        ]
        # noqa-note: kept inline for clarity

    def padded_only():
        return [
            {"subquestion_id": "sq0", "body": (BODY_PAD + " ") * 30},
        ]
        # noqa-note: kept inline for clarity

    full_out = {"answers": answers_full(), "evidence": [{"evidence_class": "ev0", "cites": "probe"}]}
    pad_out = {"answers": padded_only(), "evidence": []}
    r_full = score_output(o, full_out)
    r_pad = score_output(o, pad_out)
    checks["complete_reaches_threshold"] = r_full["score"] >= THRESHOLD
    checks["complete_score_is_1"] = r_full["score"] == 1.0
    checks["padded_below_threshold"] = r_pad["score"] < THRESHOLD
    checks["padded_score_is_0"] = r_pad["score"] == 0.0
    checks["padding_is_heavier"] = r_pad["word_count"] > r_full["word_count"]

    # Extra undeclared padding must not move a complete score.
    full_plus_pad = {
        "answers": answers_full() + [{"subquestion_id": "undeclared", "body": (BODY_PAD + " ") * 5}],
        "evidence": [{"evidence_class": "ev0", "cites": "probe"}],
    }
    r_extra = score_output(o, full_plus_pad)
    checks["extra_padding_score_unchanged"] = r_extra["score"] == r_full["score"]

    # Empty declared axis must be NOT-CHECKED and never gate.
    empty_obj = {"subquestions": [], "required_categories": [], "evidence_classes": []}
    r_empty = score_output(empty_obj, {"answers": [], "evidence": []})
    checks["empty_axes_not_checked_never_gates"] = (
        r_empty["status"] == "NOT-CHECKED" and r_empty["gate_fires"] is False
    )

    out = {
        "probe": "probe2_padding_both_states",
        "unit": "TST-0282",
        "complete_score": r_full["score"],
        "complete_word_count": r_full["word_count"],
        "padded_score": r_pad["score"],
        "padded_word_count": r_pad["word_count"],
        "threshold": THRESHOLD,
        "checks": dict(sorted(checks.items())),
        "ok": all(checks.values()),
    }
    (HERE / "probe2-padding.raw.txt").write_text(
        json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(out, sort_keys=True))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
