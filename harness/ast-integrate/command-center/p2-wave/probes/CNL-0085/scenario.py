#!/usr/bin/env python3
"""Scripted mid-deliberation council used by CNL-0085 probes."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from intervention import CouncilRun  # noqa: E402

QUESTION = "Should we ship generated-SSOT for typed projections?"
CHAIR = "seat.chair"
PROTOCOL = "protocol.catalog-class"
ROSTER = ["seat.chair", "seat.skeptic", "seat.advocate"]
WEIGHTS = {"seat.chair": 1, "seat.skeptic": 1, "seat.advocate": 1}
SEEDS = {
    "sampling": "seed-sampling-cnl0085",
    "tool_order": "seed-tool-order-cnl0085",
    "wall_clock": "seed-wall-clock-cnl0085",
    "recruit": "seed-recruit-cnl0085",
}
DISSENT = "dissent-keep: generated-SSOT is not a lossless encoding of the estate"


def scripted_run(*, run_id: str = "run-cnl0085-demo") -> CouncilRun:
    run = CouncilRun.new(
        run_id=run_id,
        question=QUESTION,
        chair_id=CHAIR,
        protocol_id=PROTOCOL,
        roster=ROSTER,
        vote_weights=WEIGHTS,
        seeds=SEEDS,
        max_rounds=8,
    )
    run.apply_event({"type": "round_open", "round": 1})
    run.apply_event(
        {"type": "vote", "seat": "seat.advocate", "value": "yes", "round": 1}
    )
    run.apply_event(
        {"type": "vote", "seat": "seat.skeptic", "value": "no", "round": 1}
    )
    run.apply_event({"type": "minority_report", "seat": "seat.skeptic", "text": DISSENT})
    return run


OPS = {
    "evidence_add": {
        "class": "evidence_add",
        "evidence_id": "ev.owner.extra-corpus",
        "text": "append-only extra citation; does not rewrite round-1 votes",
    },
    "budget_extend": {
        "class": "budget_extend",
        "field": "max_rounds",
        "old": 8,
        "new": 12,
    },
    "question_change": {
        "class": "question_change",
        "from": QUESTION,
        "to": "Should we delete the council runtime instead?",
    },
    "chair_replace": {
        "class": "chair_replace",
        "from": CHAIR,
        "to": "seat.advocate",
    },
    "quiet_question_change": {
        "class": "question_change",
        "mode": "continue",
        "from": QUESTION,
        "to": "Should we delete the council runtime instead?",
    },
    "evidence_rewrite": {
        "class": "evidence_add",
        "mutates_event_id": "minority_report",
        "text": "attempt to silently rewrite dissent",
    },
}
