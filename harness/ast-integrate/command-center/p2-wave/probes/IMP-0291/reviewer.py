"""Independent reviewer for IMP-0291: re-score the 40 labelled ideas.

Starts from the public canonicalize_mechanism / IdeaLedger API and the
labelled fixture texts. Does not import the author's pass/fail helper
beyond the gold labels on the fixture tuples.
"""
from __future__ import annotations

from council.protocol.brainstorm import (
    IdeaLedger,
    canonicalize_mechanism,
    pairwise_grouping_score,
)
from fixtures import LABELLED_40


def review_labelled_grouping() -> dict:
    gold: list[str] = []
    via_ledger: list[str] = []
    via_direct: list[str] = []
    ledger = IdeaLedger()
    for _idea_id, family, author, rnd, text in LABELLED_40:
        gold.append(family)
        via_direct.append(canonicalize_mechanism(text))
        via_ledger.append(
            ledger.append(author=author, round=rnd, text=text).canonical_mechanism
        )
    score_ledger = pairwise_grouping_score(gold, via_ledger)
    score_direct = pairwise_grouping_score(gold, via_direct)
    passed = bool(
        score_ledger["pass"]
        and score_direct["pass"]
        and score_ledger["f1"] == 1.0
        and len(LABELLED_40) == 40
        and ledger.unique_ideas() == 8
    )
    return {
        "reviewer_id": "IMP-0291-reviewer-labelled-grouping",
        "independent": True,
        "fresh_context": True,
        "starts_from": "tests/public-api",
        "pass": passed,
        "verdict": "PASS" if passed else "FAIL",
        "ledger_score": score_ledger,
        "direct_score": score_direct,
        "mechanism_distinct": ledger.unique_ideas(),
        "labelled": len(LABELLED_40),
    }
