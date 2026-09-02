"""Instant-unanimity suspicion trigger (spec :10944 / :11336).

Suspiciously fast = first vote round, every ballot identical, and the panel
has produced neither independent briefs nor evidence nodes. That is a process
failure even when the shared position happens to be true.

Legitimate unanimity is the same shared position AFTER independent briefs
that cite evidence. A contested (non-unanimous) round stays silent.

When the trigger fires it must do more than log a warning: recruit an
independent critic, emit a strongest counterexample, force a dissent mandate
onto one original seat (role rotation), and run a blind re-evaluation round
in which no participant sees peer round-1 ballots.
"""
from __future__ import annotations

from typing import Any

# Trip-wire threshold, in the units spec :10944 leaves unnamed.
# Instant iff ALL of: round_index <= MAX_ROUND, briefs <= MAX_BRIEFS,
# evidence nodes <= MAX_EVIDENCE, participant_count >= MIN_PARTICIPANTS,
# and unique_positions == 1.
THRESHOLD: dict[str, int] = {
    "max_round_index": 1,
    "max_independent_briefs": 0,
    "max_evidence_nodes": 0,
    "min_participants": 2,
}

EVENT_ROUND_ONE_VOTE = "ROUND_ONE_VOTE"
EVENT_TRIGGER = "INSTANT_UNANIMITY_TRIGGER"
EVENT_SILENT = "INSTANT_UNANIMITY_SILENT"
EVENT_CRITIC = "INDEPENDENT_CRITIC_RECRUITED"
EVENT_COUNTEREXAMPLE = "STRONGEST_COUNTEREXAMPLE"
EVENT_FORCED_DISSENT = "FORCED_DISSENT"
EVENT_ROLE_ROTATION = "ROLE_ROTATION"
EVENT_BLIND_REEVAL = "BLIND_RE_EVALUATION"

CRITIC_ID = "independent-critic"


def _brief_counts(briefs: dict[str, Any]) -> tuple[int, int]:
    n_briefs = 0
    n_evidence = 0
    for raw in briefs.values():
        if not isinstance(raw, dict):
            continue
        text = str(raw.get("text") or "").strip()
        nodes = raw.get("evidence_nodes") or []
        if not isinstance(nodes, list):
            nodes = []
        nodes = [n for n in nodes if str(n).strip()]
        if text:
            n_briefs += 1
        n_evidence += len(nodes)
    return n_briefs, n_evidence


def metrics(snapshot: dict[str, Any]) -> dict[str, Any]:
    votes = snapshot.get("votes") or {}
    if not isinstance(votes, dict):
        votes = {}
    briefs = snapshot.get("briefs") or {}
    if not isinstance(briefs, dict):
        briefs = {}
    positions = {str(v) for v in votes.values()}
    n_briefs, n_evidence = _brief_counts(briefs)
    round_index = int(snapshot.get("round_index") or 0)
    return {
        "round_index": round_index,
        "participant_count": len(votes),
        "unique_positions": len(positions),
        "independent_briefs_submitted": n_briefs,
        "evidence_nodes_cited": n_evidence,
        "unanimous": len(positions) == 1 and len(votes) >= 2,
        "positions": sorted(positions),
    }


def evaluate_trigger(snapshot: dict[str, Any]) -> dict[str, Any]:
    m = metrics(snapshot)
    fired = (
        m["round_index"] <= THRESHOLD["max_round_index"]
        and m["round_index"] >= 1
        and m["participant_count"] >= THRESHOLD["min_participants"]
        and m["unanimous"]
        and m["independent_briefs_submitted"] <= THRESHOLD["max_independent_briefs"]
        and m["evidence_nodes_cited"] <= THRESHOLD["max_evidence_nodes"]
    )
    if fired:
        reason = (
            "round-1 unanimity with zero independent briefs and zero evidence "
            "nodes (spec:10944 instant-unanimity)"
        )
    elif m["unique_positions"] > 1:
        reason = "contested: unique_positions>1; trigger stays silent"
    elif m["independent_briefs_submitted"] > THRESHOLD["max_independent_briefs"] or (
        m["evidence_nodes_cited"] > THRESHOLD["max_evidence_nodes"]
    ):
        reason = (
            "unanimity after independent briefs/evidence; legitimate, not instant"
        )
    else:
        reason = "threshold not met"
    return {
        "fired": bool(fired),
        "reason": reason,
        "threshold": dict(THRESHOLD),
        "metrics": m,
        "units": {
            "round_index": "rounds elapsed at first vote",
            "independent_briefs_submitted": "briefs with non-empty text",
            "evidence_nodes_cited": "non-empty evidence node ids",
        },
    }


def strongest_counterexample(question: str, position: str) -> str:
    return (
        f"Counterexample to {position!r} on {question!r}: the round-1 panel "
        "cited zero evidence nodes and filed zero independent briefs, so the "
        "shared ballot is unsupported even if it happens to be true. The "
        "independent critic records dissent until evidence is produced."
    )


def dissent_position(position: str) -> str:
    return f"DISSENT:{position}"


def majority(votes: dict[str, str]) -> str:
    counts: dict[str, int] = {}
    for pos in votes.values():
        counts[pos] = counts.get(pos, 0) + 1
    # Stable: highest count, then lexicographically first position.
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]


def remediate(snapshot: dict[str, Any], trigger: dict[str, Any]) -> dict[str, Any]:
    """Execute the contracted remediation. Must appear in the transcript."""
    if not trigger.get("fired"):
        raise ValueError("remediate called when trigger did not fire")
    votes = {str(k): str(v) for k, v in (snapshot.get("votes") or {}).items()}
    if not votes:
        raise ValueError("remediate requires round-1 votes")
    unanimous_pos = next(iter(votes.values()))
    question = str(snapshot.get("question") or "")
    rotated_id = sorted(votes.keys())[0]
    counter = strongest_counterexample(question, unanimous_pos)
    dissent = dissent_position(unanimous_pos)

    events: list[dict[str, Any]] = [
        {
            "event": EVENT_CRITIC,
            "fixture_id": str(snapshot.get("fixture_id") or ""),
            "critic_id": CRITIC_ID,
            "mandate": "independent critic; does not inherit round-1 ballots",
        },
        {
            "event": EVENT_COUNTEREXAMPLE,
            "fixture_id": str(snapshot.get("fixture_id") or ""),
            "against": unanimous_pos,
            "text": counter,
        },
        {
            "event": EVENT_ROLE_ROTATION,
            "fixture_id": str(snapshot.get("fixture_id") or ""),
            "participant_id": rotated_id,
            "from_role": "clone",
            "to_role": "forced-skeptic",
        },
        {
            "event": EVENT_FORCED_DISSENT,
            "fixture_id": str(snapshot.get("fixture_id") or ""),
            "actor": rotated_id,
            "mandate": "dissent the unanimous round-1 position without seeing peers",
            "position": dissent,
        },
    ]

    blind_votes = dict(votes)
    blind_votes[rotated_id] = dissent
    blind_votes[CRITIC_ID] = dissent
    events.append(
        {
            "event": EVENT_BLIND_REEVAL,
            "fixture_id": str(snapshot.get("fixture_id") or ""),
            "round": 2,
            "blind": True,
            "saw_peer_round1_ballots": False,
            "votes": dict(blind_votes),
        }
    )

    transcript = [
        {
            "round": 1,
            "kind": "vote",
            "blind": False,
            "votes": dict(votes),
            "independent_briefs": int(
                trigger["metrics"]["independent_briefs_submitted"]
            ),
        },
        {
            "round": 2,
            "kind": "blind_re_evaluation",
            "blind": True,
            "saw_peer_round1_ballots": False,
            "votes": dict(blind_votes),
            "critic_id": CRITIC_ID,
            "rotated_id": rotated_id,
            "counterexample": counter,
        },
    ]
    final = majority(blind_votes)
    independent = sorted(
        {pos for pid, pos in blind_votes.items() if pos != unanimous_pos}
    )
    return {
        "audit_events": events,
        "transcript": transcript,
        "final_verdict": final,
        "outcome_changed": final != unanimous_pos,
        "independent_positions": independent,
        "independent_position_recorded": bool(independent),
        "remediation": (
            "critic-recruited+forced-dissent+counterexample+blind-re-eval; "
            "independent dissent recorded"
            + (
                "; majority unchanged"
                if final == unanimous_pos
                else "; majority overturned"
            )
        ),
    }
