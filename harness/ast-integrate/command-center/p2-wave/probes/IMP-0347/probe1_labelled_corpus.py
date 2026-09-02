#!/usr/bin/env python3
"""Probe 1: labelled 50-pair corpus; precision and recall reported separately.

Negative control in the same run: every sincere change-of-mind pair must
stay unflagged (false-positive rate published as a number).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.antifail.corpus import labelled_corpus  # noqa: E402
from council.antifail.strategic import evaluate_ballot, score_corpus  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0347-probe1 {msg}")
    return 1


def main() -> int:
    corpus = labelled_corpus()
    if corpus["n_pairs"] != 50:
        return fail(f"n_pairs={corpus['n_pairs']} want 50")

    scored = score_corpus(corpus)
    report = {
        "probe": "probe1-labelled-corpus",
        "unit_id": "IMP-0347",
        "n_pairs": scored["n_pairs"],
        "label_counts": corpus["label_counts"],
        "precision": scored["precision"],
        "recall": scored["recall"],
        "metrics": scored["metrics"],
        "change_of_mind_n": scored["change_of_mind_n"],
        "change_of_mind_false_positives": scored["change_of_mind_false_positives"],
        "change_of_mind_fpr": scored["change_of_mind_fpr"],
        "profile_reports": scored["profile_reports"],
    }
    print(json.dumps(report, indent=2, sort_keys=True))

    if scored["n_pairs"] != 50:
        return fail("scored n_pairs drifted")
    if scored["precision"] != 1.0:
        return fail(f"precision={scored['precision']} (must be reported and equal 1.0 on this corpus)")
    if scored["recall"] != 1.0:
        return fail(f"recall={scored['recall']} (must be reported and equal 1.0 on this corpus)")
    if scored["change_of_mind_n"] != 10:
        return fail(f"change_of_mind_n={scored['change_of_mind_n']}")
    if scored["change_of_mind_fpr"] != 0.0:
        return fail(
            f"change_of_mind_fpr={scored['change_of_mind_fpr']} "
            f"fps={scored['change_of_mind_false_positives']}"
        )

    # Isolated negative control: CM-00 is a change of mind, not a misreport.
    cm = next(p for p in corpus["pairs"] if p["id"] == "CM-00")
    det = evaluate_ballot(cm)
    if det["strategic"] or det["strategic_vote"]:
        return fail(f"negative control CM-00 flagged {det}")
    if not det["change_of_mind"]:
        return fail("CM-00 not classified as change_of_mind")
    if det["implied_stance"] != "nay":
        return fail(f"CM-00 implied {det['implied_stance']} (updated stance not used)")

    sv = next(p for p in corpus["pairs"] if p["id"] == "SV-00")
    det_sv = evaluate_ballot(sv)
    if not det_sv["strategic_vote"]:
        return fail(f"planted SV-00 silent {det_sv}")

    # Detector must not read labels: a copy with labels stripped must match.
    stripped = {
        "pairs": [{k: v for k, v in p.items() if k != "label"} for p in corpus["pairs"]],
        "profiles": corpus["profiles"],
    }
    # score_corpus treats missing labels as not-positive; instead compare
    # predicted strategic flags on labelled vs stripped evaluate_ballot.
    from council.antifail.strategic import evaluate_profile  # noqa: E402

    preds_labelled = {r["id"]: r["pred_strategic"] for r in scored["rows"]}
    profile_dets = {}
    for prof in stripped["profiles"]:
        for det in evaluate_profile(prof)["detections"]:
            profile_dets[det["participant_id"]] = det
    mismatch = []
    for p in stripped["pairs"]:
        pid = p["id"]
        if pid in profile_dets:
            pred = bool(profile_dets[pid]["strategic"])
        else:
            pred = bool(evaluate_ballot(p)["strategic"])
        if pred != preds_labelled[pid]:
            mismatch.append(pid)
    if mismatch:
        return fail(f"label-stripped predictions drifted {mismatch[:8]}")

    print("SUCCESS:IMP-0347-probe1 precision and recall reported; change-of-mind FPR=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
