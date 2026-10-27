"""Deterministic council-run fixtures for IMP-0323.

Labels (easy/hard) exist for evaluation only. The detector never reads them.
Quotas and idea/objection lists are the only load-bearing fields.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"

EASY_MIN_IDEAS = 2
EASY_MIN_OBJ = 1
HARD_MIN_IDEAS = 8
HARD_MIN_OBJ = 4


def _items(prefix: str, n: int, *, kind: str) -> list[dict[str, str]]:
    stem = "obj" if kind == "objection" else "idea"
    return [
        {
            "id": f"{prefix}-{stem}-{i}",
            "canonical_id": f"{prefix}-{stem}-{i}",
            "text": f"{prefix} {kind} {i}",
        }
        for i in range(n)
    ]


def _run(
    rid: str,
    *,
    label: str,
    question: str,
    round_index: int,
    min_ideas: int,
    min_obj: int,
    n_ideas: int,
    n_obj: int,
    converged: bool = True,
    ideas: list[dict[str, str]] | None = None,
    objections: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    return {
        "id": rid,
        "label": label,
        "question_class": label,
        "question": question,
        "converged": converged,
        "round_index": round_index,
        "divergence": {
            "min_unique_ideas": min_ideas,
            "min_objections": min_obj,
        },
        "ideas": ideas if ideas is not None else _items(rid, n_ideas, kind="idea"),
        "objections": (
            objections if objections is not None else _items(rid, n_obj, kind="objection")
        ),
    }


EASY_QUESTIONS = [
    "What is 2+2 in ordinary arithmetic?",
    "What is the capital of France?",
    "At 1 atm, at what temperature does pure water boil in Celsius?",
    "Is the integer 7 prime?",
    "What does HTTP status 404 mean?",
    "In Python, what does len([]) return?",
    "How many bits are in a byte?",
    "What is the chemical formula of water?",
    "Which planet is third from the Sun?",
    "Does a valid JSON object start with '{' or with '['?",
    "What is 10 in binary?",
    "Is an empty Python list truthy or falsy?",
]

HARD_QUESTIONS = [
    "Design a globally consistent multi-region consensus protocol with partition tolerance documented.",
    "Formally specify a distributed lock that cannot livelock under Fair-loss links.",
    "Propose a tax treatment for cross-border staking rewards that survives two jurisdictions.",
    "Enumerate distinct failure modes of a two-phase commit coordinator crash after PREPARE.",
    "Argue for or against CRDTs as the storage model for a collaborative CAD tool.",
    "Specify an objection-complete threat model for a threshold-signing custody service.",
    "Compare three mechanically different approaches to online schema migration with zero downtime.",
    "What stopping rule should a research council use when genuine disconfirming evidence may not exist?",
]


def easy_control_set() -> list[dict[str, Any]]:
    rows = []
    for i, q in enumerate(EASY_QUESTIONS, start=1):
        rid = f"easy-{i:02d}"
        rows.append(
            _run(
                rid,
                label="easy",
                question=q,
                round_index=1 if i <= 10 else 1 + (i % 3),
                min_ideas=EASY_MIN_IDEAS,
                min_obj=EASY_MIN_OBJ,
                n_ideas=EASY_MIN_IDEAS,
                n_obj=EASY_MIN_OBJ,
            )
        )
    return rows


def hard_round1() -> dict[str, Any]:
    return _run(
        "hard-round1",
        label="hard",
        question=HARD_QUESTIONS[0],
        round_index=1,
        min_ideas=HARD_MIN_IDEAS,
        min_obj=HARD_MIN_OBJ,
        n_ideas=1,
        n_obj=0,
    )


def twenty_runs() -> list[dict[str, Any]]:
    """Twenty runs with quota-attainment recorded at convergence.

    Mix:
      1-8   easy, round 1, quotas met
      9-12  hard, round 1, quotas unmet
      13-14 hard, late rounds, quotas unmet (round-count would miss)
      15-18 hard, late rounds, quotas met
      19    ideas unmet / objections met
      20    padded duplicate canonical_ids (8 records, 1 unique idea)
    """
    easy = easy_control_set()[:8]
    hard_early = [
        _run(
            f"hard-early-{i}",
            label="hard",
            question=HARD_QUESTIONS[i],
            round_index=1,
            min_ideas=HARD_MIN_IDEAS,
            min_obj=HARD_MIN_OBJ,
            n_ideas=1,
            n_obj=0 if i % 2 == 0 else 1,
        )
        for i in range(1, 5)
    ]
    hard_late_unmet = [
        _run(
            "hard-late-unmet-1",
            label="hard",
            question=HARD_QUESTIONS[5],
            round_index=5,
            min_ideas=HARD_MIN_IDEAS,
            min_obj=HARD_MIN_OBJ,
            n_ideas=3,
            n_obj=1,
        ),
        _run(
            "hard-late-unmet-2",
            label="hard",
            question=HARD_QUESTIONS[6],
            round_index=6,
            min_ideas=HARD_MIN_IDEAS,
            min_obj=HARD_MIN_OBJ,
            n_ideas=2,
            n_obj=0,
        ),
    ]
    hard_ok = [
        _run(
            f"hard-ok-{i}",
            label="hard",
            question=HARD_QUESTIONS[i % len(HARD_QUESTIONS)],
            round_index=3 + i,
            min_ideas=HARD_MIN_IDEAS,
            min_obj=HARD_MIN_OBJ,
            n_ideas=HARD_MIN_IDEAS,
            n_obj=HARD_MIN_OBJ,
        )
        for i in range(1, 5)
    ]
    ideas_only = _run(
        "hard-ideas-short",
        label="hard",
        question=HARD_QUESTIONS[7],
        round_index=3,
        min_ideas=HARD_MIN_IDEAS,
        min_obj=HARD_MIN_OBJ,
        n_ideas=3,
        n_obj=HARD_MIN_OBJ,
    )
    padded = _run(
        "hard-padded-dups",
        label="hard",
        question=HARD_QUESTIONS[0],
        round_index=1,
        min_ideas=HARD_MIN_IDEAS,
        min_obj=HARD_MIN_OBJ,
        n_ideas=0,
        n_obj=0,
        ideas=[
            {
                "id": f"pad-{i}",
                "canonical_id": "raft-everywhere",
                "text": f"Use Raft (wording {i})",
            }
            for i in range(8)
        ],
        objections=[],
    )
    rows = easy + hard_early + hard_late_unmet + hard_ok + [ideas_only, padded]
    if len(rows) != 20:
        raise RuntimeError(f"expected 20 runs, got {len(rows)}")
    return rows


def not_converged() -> dict[str, Any]:
    return _run(
        "still-running",
        label="hard",
        question=HARD_QUESTIONS[2],
        round_index=1,
        min_ideas=HARD_MIN_IDEAS,
        min_obj=HARD_MIN_OBJ,
        n_ideas=1,
        n_obj=0,
        converged=False,
    )


def undeclared_quotas() -> dict[str, Any]:
    row = hard_round1()
    row = dict(row)
    row["id"] = "no-quotas"
    row["divergence"] = {}
    return row


def dump_json() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    docs = {
        "twenty-runs.json": twenty_runs(),
        "easy-control.json": easy_control_set(),
        "hard-round1.json": hard_round1(),
        "not-converged.json": not_converged(),
        "undeclared-quotas.json": undeclared_quotas(),
    }
    for name, doc in docs.items():
        (FIXTURES / name).write_text(
            json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )


def all_named() -> dict[str, Any]:
    return {
        "hard-round1": hard_round1(),
        "not-converged": not_converged(),
        "undeclared-quotas": undeclared_quotas(),
    }
