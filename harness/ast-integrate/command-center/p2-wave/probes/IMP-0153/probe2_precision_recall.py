#!/usr/bin/env python3
"""Probe 2: precision and recall as computed numbers on the 30-doc labelled set.

The floats MUST equal tp/(tp+fp) and tp/(tp+fn) from this run. A hardcoded
0.93 in the receipt is a fail if it disagrees with the live confusion matrix.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

import corpus as C  # noqa: E402
from workflow_scout.adapters import prose as P  # noqa: E402

ART = REPO / "command-center" / "receipts" / "IMP-0153.json"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})
FLOOR = 0.8


def main() -> int:
    C.materialize()
    impl = {P.norm_id(x) for x in C.IMPLEMENTED_IDS}
    docs = C.labelled_docs()
    if len(docs) != 30:
        print(f"FAILED:IMP-0153-probe2 labelled set size {len(docs)} want=30")
        return 1
    gold_pos = sum(1 for d in docs if d["gold_harvest"])
    if gold_pos < 8:
        print(f"FAILED:IMP-0153-probe2 gold harvest count {gold_pos} too small")
        return 1

    report = P.score_labelled(docs, implemented=impl, distinguish_use_mention=True)
    den_p = report.tp + report.fp
    den_r = report.tp + report.fn
    if den_p <= 0 or den_r <= 0:
        print("FAILED:IMP-0153-probe2 confusion matrix has empty precision/recall denom")
        print(json.dumps(report.as_dict(), indent=2)[:3000])
        return 1
    prec_live = report.tp / den_p
    rec_live = report.tp / den_r
    if abs(prec_live - report.precision) > 1e-12 or abs(rec_live - report.recall) > 1e-12:
        print("FAILED:IMP-0153-probe2 report floats are not the computed ratios")
        return 1
    if report.precision < FLOOR or report.recall < FLOOR:
        print(
            f"FAILED:IMP-0153-probe2 precision={report.precision} "
            f"recall={report.recall} below floor {FLOOR}"
        )
        print(json.dumps(report.as_dict(), indent=2)[:4000])
        return 1

    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        try:
            doc = json.loads(text)
        except json.JSONDecodeError as exc:
            print(f"FAILED:IMP-0153-probe2 receipt unparseable {exc}")
            return 1
        if str(doc.get("state") or "").upper() in NOT_DELIVERING:
            print(f"FAILED:IMP-0153-probe2 self-declared {doc.get('state')}")
            return 1
        if "SUCCESS:IMP-0153" not in text:
            print("FAILED:IMP-0153-probe2 sentinel absent")
            return 1
        scored = doc.get("labelled_control") or doc.get("report") or {}
        if isinstance(scored, dict) and "labelled_control" in doc:
            scored = doc["labelled_control"]
        rprec = scored.get("precision") if isinstance(scored, dict) else None
        rrec = scored.get("recall") if isinstance(scored, dict) else None
        if rprec is None or rrec is None:
            print("FAILED:IMP-0153-probe2 receipt missing computed precision/recall")
            return 1
        if abs(float(rprec) - report.precision) > 1e-9 or abs(float(rrec) - report.recall) > 1e-9:
            print(
                "FAILED:IMP-0153-probe2 receipt P/R disagree with live matrix "
                f"receipt=({rprec},{rrec}) live=({report.precision},{report.recall})"
            )
            return 1

    payload = {
        "n_docs": report.n_docs,
        "tp": report.tp,
        "fp": report.fp,
        "fn": report.fn,
        "tn": report.tn,
        "precision": report.precision,
        "recall": report.recall,
        "precision_formula": f"{report.tp}/({report.tp}+{report.fp})",
        "recall_formula": f"{report.tp}/({report.tp}+{report.fn})",
        "floor": FLOOR,
        "pass": True,
        "probe": "probe2-precision-recall-labelled-30",
        "unit_id": "IMP-0153",
        "fp_paths": [d.path for d in report.per_doc if d.outcome == "fp"],
        "fn_paths": [d.path for d in report.per_doc if d.outcome == "fn"],
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"SUCCESS:IMP-0153-probe2 precision={report.precision:.4f} "
        f"recall={report.recall:.4f} n=30"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
