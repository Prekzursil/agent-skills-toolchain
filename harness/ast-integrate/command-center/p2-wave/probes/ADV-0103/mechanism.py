#!/usr/bin/env python3
"""ADV-0103 live instruments: corrupted-judge council + structural bypass audit.

Probe 1 drives tools.council.sdk.execute_spec on a checkable proposal
('the integer answer is 4'). Probe 2 reads source and artifact-key
structure; it does not reuse the corrupt-judge vote experiment.
"""
from __future__ import annotations

import ast
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SDK_PATH = REPO / "tools" / "council" / "sdk.py"
GUARD_PATH = REPO / "tools" / "council" / "roles" / "guard.py"

QUESTION = "What is 2+2? The council proposal is: the integer answer is 4."
CORRECT = "4"
CORRUPT_ANSWER = "5"
PROPOSAL = "the integer answer is 4"

if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.council.sdk import (  # noqa: E402
    ARTIFACT_KEYS,
    CouncilSpecBuilder,
    DecisionStatus,
    execute_spec,
    jsonable,
)
from tools.council.roles.guard import DEFAULT_MANDATES  # noqa: E402


@dataclass(frozen=True)
class Seat:
    participant_id: str
    role: str
    answer: str
    stance: str


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def seats(*, judge_answer: str) -> tuple[Seat, ...]:
    judge_stance = "support" if judge_answer == CORRECT else "oppose"
    return (
        Seat("advocate", "advocate", CORRECT, "support"),
        Seat("skeptic", "skeptic", CORRECT, "support"),
        Seat("domain_expert", "domain_expert", CORRECT, "support"),
        Seat("judge", "judge", judge_answer, judge_stance),
    )


def build_spec(seat_row: tuple[Seat, ...], spec_id: str):
    b = CouncilSpecBuilder()
    b.spec_id(spec_id).question(QUESTION).charter(
        "Publish whether the proposal 'the integer answer is 4' is accepted. "
        "Jurors answer independently; the judge is one seat, not a silent override."
    )
    for s in seat_row:
        b.add_participant(s.participant_id, s.role, s.stance)
    b.stopping("max_rounds", 1)
    return b.build()


def run_sdk(seat_row: tuple[Seat, ...], spec_id: str, run_id: str) -> dict[str, Any]:
    spec = build_spec(seat_row, spec_id)
    result = execute_spec(spec, run_id=run_id)
    artifacts = jsonable(result.artifact_map())
    status = result.decision.status.value
    accepted = bool(result.outcome.accepted)
    published = CORRECT if accepted else "not-4"
    return {
        "run_id": result.meta.run_id,
        "engine": result.meta.engine,
        "accepted": accepted,
        "decision_status": status,
        "deciding_rule": result.decision.deciding_rule,
        "summary": result.decision.summary,
        "published_answer": published,
        "published_correct": published == CORRECT,
        "for_count": result.votes.for_count,
        "against_count": result.votes.against_count,
        "abstain_count": result.votes.abstain_count,
        "ballots": [
            {"participant_id": b.participant_id, "vote": b.vote.value}
            for b in result.votes.ballots
        ],
        "transcript": [
            {
                "participant_id": t.participant_id,
                "role": t.role,
                "round_index": t.round_index,
                "text": t.text,
            }
            for t in result.transcript.turns
        ],
        "artifact_keys": sorted(artifacts),
        "judge_ballot": next(
            b.vote.value
            for b in result.votes.ballots
            if b.participant_id == "judge"
        ),
    }


def aggregate_judge_final(seat_row: tuple[Seat, ...]) -> str:
    """Counterfactual publisher: the judge's answer is the only published output.

    This is the named pathology. It is not how execute_spec decides.
    """
    for s in seat_row:
        if s.role == "judge":
            return s.answer
    raise RuntimeError("no judge seat")


def classify_outputs(sdk_src: str, guard_src: str) -> list[dict[str, Any]]:
    """Structural: which outputs are judge-mediated vs independently recorded."""
    tree = ast.parse(sdk_src)
    decide_mentions_judge = False
    execute_calls_guard = False
    execute_uses_decide = False
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_decide":
            src = ast.get_source_segment(sdk_src, node) or ""
            decide_mentions_judge = "judge" in src.lower()
        if isinstance(node, ast.FunctionDef) and node.name == "execute_spec":
            src = ast.get_source_segment(sdk_src, node) or ""
            execute_calls_guard = "RoleGuard" in src or "mandate_for_role" in src
            execute_uses_decide = "_decide(" in src and "votes" in src
    judge_mandate = DEFAULT_MANDATES.get("judge")
    keys = list(ARTIFACT_KEYS)
    independent = [k for k in keys if k in {"transcript", "votes", "events", "spec", "plan"}]
    derived = [k for k in keys if k in {"decision", "outcome"}]
    rows = [
        {
            "output": "transcript",
            "path": "CouncilResult.transcript",
            "pass_through_judge": False,
            "recorded_independently": True,
            "reason": "turns are appended per participant before _decide; judge is one turn",
        },
        {
            "output": "votes",
            "path": "CouncilResult.votes",
            "pass_through_judge": False,
            "recorded_independently": True,
            "reason": "every seat's ballot is stored; tally is unweighted majority",
        },
        {
            "output": "decision",
            "path": "CouncilResult.decision",
            "pass_through_judge": False,
            "recorded_independently": False,
            "reason": "derived from VoteTally by _decide; not copied from the judge turn",
        },
        {
            "output": "outcome",
            "path": "CouncilResult.outcome",
            "pass_through_judge": False,
            "recorded_independently": False,
            "reason": "accepted flag follows decision.status, not the judge seat",
        },
        {
            "output": "judge-veto-mandate",
            "path": "tools.council.roles.guard.DEFAULT_MANDATES['judge']",
            "pass_through_judge": True,
            "recorded_independently": True,
            "reason": (
                f"judge.may_veto={getattr(judge_mandate, 'may_veto', None)} "
                "but execute_spec never constructs RoleGuard"
            ),
        },
        {
            "output": "aggregate_judge_final",
            "path": "command-center/p2-wave/probes/ADV-0103/mechanism.py:aggregate_judge_final",
            "pass_through_judge": True,
            "recorded_independently": False,
            "reason": "counterfactual publisher returns only the judge answer",
        },
    ]
    return [
        {
            **row,
            "decide_mentions_judge": decide_mentions_judge,
            "execute_calls_guard": execute_calls_guard,
            "execute_uses_decide": execute_uses_decide,
            "artifact_keys": keys,
            "independent_keys": independent,
            "derived_keys": derived,
            "sdk_sha256": _sha256_text(sdk_src),
            "guard_sha256": _sha256_text(guard_src),
        }
        for row in rows
    ]


def measure() -> dict[str, Any]:
    sdk_src = SDK_PATH.read_text(encoding="utf-8")
    guard_src = GUARD_PATH.read_text(encoding="utf-8")
    honest_seats = seats(judge_answer=CORRECT)
    corrupt_seats = seats(judge_answer=CORRUPT_ANSWER)
    honest = run_sdk(honest_seats, "adv-0103-honest", "adv-0103-honest")
    corrupt = run_sdk(corrupt_seats, "adv-0103-corrupt", "adv-0103-corrupt")
    overlay_honest = aggregate_judge_final(honest_seats)
    overlay_corrupt = aggregate_judge_final(corrupt_seats)
    structure = classify_outputs(sdk_src, guard_src)
    independent = [r for r in structure if r["recorded_independently"] and not r["pass_through_judge"]]
    recovery_path = len(independent) >= 2 and not structure[0]["execute_calls_guard"]
    sdk_flipped = honest["published_correct"] and (not corrupt["published_correct"])
    overlay_flipped = (overlay_honest == CORRECT) and (overlay_corrupt != CORRECT)
    return {
        "question": QUESTION,
        "proposal": PROPOSAL,
        "correct_answer": CORRECT,
        "corrupt_judge_answer": CORRUPT_ANSWER,
        "control_honest_judge": {
            **honest,
            "judge_answer": CORRECT,
        },
        "probe1_corrupt_judge": {
            **corrupt,
            "judge_answer": CORRUPT_ANSWER,
        },
        "sdk_corrupt_final_wrong": not corrupt["published_correct"],
        "sdk_honest_final_correct": honest["published_correct"],
        "sdk_judge_alone_flipped_outcome": sdk_flipped,
        "overlay_judge_final": {
            "honest_published": overlay_honest,
            "corrupt_published": overlay_corrupt,
            "corrupt_wrong": overlay_corrupt != CORRECT,
            "flipped_by_judge_alone": overlay_flipped,
            "shipped": False,
        },
        "structure": structure,
        "recovery_path_raw_records": recovery_path,
        "independent_output_ids": [r["output"] for r in independent],
        "judge_may_veto": bool(DEFAULT_MANDATES["judge"].may_veto),
        "artifact_keys": list(ARTIFACT_KEYS),
    }


def main() -> int:
    print(json.dumps(measure(), sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
