"""Naive vs locked self-improvement accept/revert.

Naive scores the candidate with whatever measure files are in the tree after
the apply. That is the implicit rule when no fingerprint lock exists.

Locked always scores against the PRE-change measure and REVERTs when the
measure fingerprint moved. Genuine SUT-only improvements still KEEP.
"""
from __future__ import annotations

from pathlib import Path

from fixtures import MEASURE_PATHS, apply_candidate, base_tree
from score import score_tree

KEEP = "KEEP"
REVERT = "REVERT"


def _with_pre_measure(after: dict[str, str], before: dict[str, str]) -> dict[str, str]:
    mixed = dict(after)
    for rel in MEASURE_PATHS:
        mixed[rel] = before[rel]
    return mixed


def decide(
    candidate_id: str,
    mode: str,
    scratch: Path,
) -> dict:
    before = base_tree()
    after = apply_candidate(before, candidate_id)
    fp_before = score_tree(before, scratch / "before")["fingerprint"]
    scored_before = score_tree(before, scratch / "score-before")
    if mode == "naive":
        scored_after = score_tree(after, scratch / "score-naive")
        fp_after = scored_after["fingerprint"]
        decision = KEEP if scored_after["reported"] > scored_before["reported"] else REVERT
        reason = "post-change-measure-score-delta"
    elif mode == "locked":
        mixed = _with_pre_measure(after, before)
        scored_after = score_tree(mixed, scratch / "score-locked")
        fp_after = score_tree(after, scratch / "fp-after")["fingerprint"]
        if fp_before != fp_after:
            decision = REVERT
            reason = "measure-fingerprint-changed"
        elif scored_after["reported"] > scored_before["reported"]:
            decision = KEEP
            reason = "pre-change-measure-improved"
        else:
            decision = REVERT
            reason = "pre-change-measure-not-improved"
    elif mode == "reject-all":
        scored_after = score_tree(after, scratch / "score-reject")
        fp_after = scored_after["fingerprint"]
        decision = REVERT
        reason = "reject-all-mutant"
    else:
        raise ValueError(f"unknown mode {mode}")
    return {
        "candidate_id": candidate_id,
        "mode": mode,
        "decision": decision,
        "reason": reason,
        "score_before": scored_before["reported"],
        "score_after": scored_after["reported"],
        "ratio_before": scored_before["ratio"],
        "ratio_after": scored_after["ratio"],
        "fp_before": fp_before,
        "fp_after": fp_after,
        "fingerprint_changed": fp_before != fp_after,
        "sut_changed": before["sut.py"] != after["sut.py"],
        "measure_changed": any(before[p] != after[p] for p in MEASURE_PATHS),
    }
