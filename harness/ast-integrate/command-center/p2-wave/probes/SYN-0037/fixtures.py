"""Planted and known-good receipt corpora for SYN-0037 detector controls."""
from __future__ import annotations


def known_good() -> list[dict]:
    """Independent authors and reviewers; acyclic; every field present."""
    return [
        {
            "path": "fixtures/known-good/G1.json",
            "doc": {
                "unit_id": "SYN-GOOD-1",
                "author_id": "author-1",
                "reviewer_id": "reviewer-1",
                "state": "SUCCESS",
            },
        },
        {
            "path": "fixtures/known-good/G2.json",
            "doc": {
                "unit_id": "SYN-GOOD-2",
                "author_id": "author-2",
                "reviewer": {"reviewer_id": "reviewer-2", "verdict": "PASS"},
                "state": "SUCCESS",
            },
        },
        {
            "path": "fixtures/known-good/G3.json",
            "doc": {
                "unit_id": "SYN-GOOD-3",
                "produced_by": {
                    "vendor": "vendor-x",
                    "model": "model-y",
                    "role": "implementer",
                },
                "reviewer": {"reviewer_id": "reviewer-1", "independent": True},
                "state": "SUCCESS",
            },
        },
    ]


def planted_self_review() -> list[dict]:
    """Same agent authored the receipt and reviewed it."""
    return known_good() + [
        {
            "path": "fixtures/planted-self-review.json",
            "doc": {
                "unit_id": "SYN-PLANT-SELF",
                "author_id": "agent-alpha",
                "reviewer": {"reviewer_id": "agent-alpha", "verdict": "PASS"},
                "state": "SUCCESS",
            },
        }
    ]


def planted_two_cycle() -> list[dict]:
    """A reviews B, B reviews A."""
    return known_good() + [
        {
            "path": "fixtures/planted-two-cycle-a.json",
            "doc": {
                "unit_id": "SYN-PLANT-C1",
                "author_id": "agent-a",
                "reviewer_id": "agent-b",
            },
        },
        {
            "path": "fixtures/planted-two-cycle-b.json",
            "doc": {
                "unit_id": "SYN-PLANT-C2",
                "author_id": "agent-b",
                "reviewer_id": "agent-a",
            },
        },
    ]


def planted_missing_reviewer() -> list[dict]:
    """Author present, reviewer_id absent — must be a violation, not a skip."""
    return known_good() + [
        {
            "path": "fixtures/planted-missing-reviewer.json",
            "doc": {
                "unit_id": "SYN-PLANT-MISS",
                "author_id": "agent-gamma",
                "state": "SUCCESS",
            },
        }
    ]


def planted_three_cycle() -> list[dict]:
    """A→B→C→A, distinct from the two-cycle plant."""
    return [
        {
            "path": "fixtures/planted-three-a.json",
            "doc": {"unit_id": "T1", "author_id": "n1", "reviewer_id": "n3"},
        },
        {
            "path": "fixtures/planted-three-b.json",
            "doc": {"unit_id": "T2", "author_id": "n2", "reviewer_id": "n1"},
        },
        {
            "path": "fixtures/planted-three-c.json",
            "doc": {"unit_id": "T3", "author_id": "n3", "reviewer_id": "n2"},
        },
    ]
