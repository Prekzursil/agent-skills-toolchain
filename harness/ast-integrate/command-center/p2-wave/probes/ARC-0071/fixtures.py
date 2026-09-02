"""Planted scoring round for ARC-0071.

ARC-0069 SCORECARDS.json and ARC-0070 AGGREGATE-RANKING.json are absent on
this worktree. This fixture is a three-judge, three-entry, three-dimension
round with four *recorded* dissents, including minority positions on a
losing entry. Labels E-alpha/E-beta/E-gamma are fixture ids, not the nine
tournament architecture names.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REVIEWER_JUDGE = "J-gamma"
WINNER = "E-alpha"
JUDGES = ("J-alpha", "J-beta", "J-gamma")
ENTRIES = ("E-alpha", "E-beta", "E-gamma")
DIMENSIONS = ("decomposability", "evidence_weight", "control_singularity")

# Majority cell scores. Recorded dissents override the dissenting judge's cell.
MAJORITY = {
    ("E-alpha", "decomposability"): 5,
    ("E-alpha", "evidence_weight"): 5,
    ("E-alpha", "control_singularity"): 4,
    ("E-beta", "decomposability"): 4,
    ("E-beta", "evidence_weight"): 4,
    ("E-beta", "control_singularity"): 3,
    ("E-gamma", "decomposability"): 3,
    ("E-gamma", "evidence_weight"): 3,
    ("E-gamma", "control_singularity"): 4,
}

# Recorded minority positions (the population the report must preserve).
RECORDED = (
    {
        "judge_id": "J-gamma",
        "entry_id": "E-alpha",
        "dimension": "decomposability",
        "score": 2,
        "majority_score": 5,
        "reasoning": (
            "The winner's lineage table is a citation list, not a "
            "decomposition into independently shippable parts."
        ),
        "evidence_citation": (
            "command-center/WORK-UNIT-CATALOG.json:ARC-0071:"
            "dissent-preservation-set-difference"
        ),
    },
    {
        "judge_id": "J-gamma",
        "entry_id": "E-alpha",
        "dimension": "evidence_weight",
        "score": 3,
        "majority_score": 5,
        "reasoning": (
            "Winner citations in this fixture are catalog sentences, not "
            "measured artifacts from a live ARC-0069 scoring round."
        ),
        "evidence_citation": (
            "command-center/p2-wave/probes/ARC-0071/fixtures.py:"
            "live-scorecards-absent"
        ),
    },
    {
        "judge_id": "J-beta",
        "entry_id": "E-gamma",
        "dimension": "control_singularity",
        "score": 1,
        "majority_score": 4,
        "reasoning": (
            "E-gamma concentrates control in two evaluators; this minority "
            "score stands even though E-gamma lost the ranking."
        ),
        "evidence_citation": (
            "command-center/p2-wave/probes/ARC-0071/fixtures.py:"
            "losing-entry-dissent-must-travel"
        ),
    },
    {
        "judge_id": "J-alpha",
        "entry_id": "E-beta",
        "dimension": "decomposability",
        "score": 2,
        "majority_score": 4,
        "reasoning": (
            "E-beta's generator boundary is specified but this round produced "
            "no generated-tree hash, so the high decomposability score is "
            "unearned."
        ),
        "evidence_citation": (
            "command-center/p2-wave/probes/ARC-0071/fixtures.py:"
            "unearned-decomposability"
        ),
    },
)


def _cell(judge_id: str, entry_id: str, dimension: str) -> dict[str, Any]:
    for rec in RECORDED:
        if (
            rec["judge_id"] == judge_id
            and rec["entry_id"] == entry_id
            and rec["dimension"] == dimension
        ):
            return {
                "dimension": dimension,
                "score": rec["score"],
                "reasoning": rec["reasoning"],
                "evidence_citation": rec["evidence_citation"],
                "dissent": True,
            }
    return {
        "dimension": dimension,
        "score": MAJORITY[(entry_id, dimension)],
        "reasoning": f"Majority cell {entry_id}/{dimension}.",
        "evidence_citation": f"fixture:majority:{entry_id}:{dimension}",
        "dissent": False,
    }


def scorecards() -> dict[str, Any]:
    cards: list[dict[str, Any]] = []
    for judge_id in JUDGES:
        for entry_id in ENTRIES:
            dims = [_cell(judge_id, entry_id, d) for d in DIMENSIONS]
            local = [
                dict(rec)
                for rec in RECORDED
                if rec["judge_id"] == judge_id and rec["entry_id"] == entry_id
            ]
            cards.append(
                {
                    "judge_id": judge_id,
                    "entry_id": entry_id,
                    "peer_scores_visible": False,
                    "dimensions": dims,
                    "dissents": local,
                }
            )
    return {
        "unit_id": "ARC-0069-fixture-for-ARC-0071",
        "schema": "arc-0071.scorecards.v1",
        "reviewer_judge_id": REVIEWER_JUDGE,
        "independence": {
            "cross_talk_before_submit": False,
            "note": (
                "Fixture independence: each card is authored in this file as "
                "a closed record. Live mtime/dispatch proof belongs to ARC-0069."
            ),
        },
        "scorecards": cards,
    }


def ranking() -> dict[str, Any]:
    return {
        "unit_id": "ARC-0070-fixture-for-ARC-0071",
        "schema": "arc-0071.aggregate-ranking.v1",
        "winner_entry_id": WINNER,
        "method": "fixture-declared-ranking (not a live Condorcet matrix)",
        "ranking": [
            {"entry_id": "E-alpha", "rank": 1, "aggregate": 14.0},
            {"entry_id": "E-beta", "rank": 2, "aggregate": 11.0},
            {"entry_id": "E-gamma", "rank": 3, "aggregate": 10.0},
        ],
        "does_not_mean": (
            "This ranking is not the Phase 3 tournament winner. ARC-0070 "
            "AGGREGATE-RANKING.json is absent; E-alpha is the fixture winner "
            "the minority report travels with."
        ),
    }


def dump(target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    (target / "SCORECARDS.json").write_text(
        json.dumps(scorecards(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (target / "AGGREGATE-RANKING.json").write_text(
        json.dumps(ranking(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
