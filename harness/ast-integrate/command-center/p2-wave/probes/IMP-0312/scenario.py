"""Scripted councils for IMP-0312 dissent conservation probes."""
from __future__ import annotations

TOKEN_ALPHA = (
    "TOKEN-DSNT-ALPHA: the proposed hatch path leaks owner credentials "
    "into the artifact bundle"
)
TOKEN_BETA = (
    "TOKEN-DSNT-BETA: ranked-choice on this ballot set elects a Condorcet loser"
)
TOKEN_GAMMA = (
    "TOKEN-DSNT-GAMMA: nested fan-in averages away the skeptic's impossibility proof"
)

MAJORITY_CLAIM = "Ship the hatch path as-is under option opt-A."


def majority() -> dict:
    return {"option_id": "opt-A", "claim": MAJORITY_CLAIM}


def _vote(pid: str, option: str, *, turn: str, round_index: int = 1, role: str = "", **extra) -> dict:
    row = {
        "turn_id": turn,
        "round_index": round_index,
        "participant_id": pid,
        "role": role,
        "kind": "vote",
        "option_id": option,
    }
    row.update(extra)
    return row


def two_dissent_council() -> list[dict]:
    """Five participants: 3 for opt-A, two attributed dissents with distinctive claims."""
    return [
        _vote("p-architect", "opt-A", turn="t-r1-p-architect", role="Architect", claim=MAJORITY_CLAIM),
        _vote("p-pragmatist", "opt-A", turn="t-r1-p-pragmatist", role="Pragmatist", claim=MAJORITY_CLAIM),
        _vote("p-critic", "opt-A", turn="t-r1-p-critic", role="Critic", claim=MAJORITY_CLAIM),
        _vote(
            "p-skeptic",
            "opt-B",
            turn="t-r1-p-skeptic",
            role="Skeptic",
            is_dissent=True,
            kind="dissent",
            claim=TOKEN_ALPHA,
            rationale=TOKEN_ALPHA,
            evidence_cites=["e-hatch-leak"],
        ),
        _vote(
            "p-auditor",
            "opt-C",
            turn="t-r1-p-auditor",
            role="Auditor",
            is_dissent=True,
            kind="dissent",
            claim=TOKEN_BETA,
            rationale=TOKEN_BETA,
            evidence_cites=["e-condorcet"],
        ),
    ]


def unanimous_council() -> list[dict]:
    """No dissent. A fabricated minority report would be a false positive."""
    return [
        _vote("p-architect", "opt-A", turn="t-u-p-architect", role="Architect", claim=MAJORITY_CLAIM),
        _vote("p-skeptic", "opt-A", turn="t-u-p-skeptic", role="Skeptic", claim=MAJORITY_CLAIM),
        _vote("p-pragmatist", "opt-A", turn="t-u-p-pragmatist", role="Pragmatist", claim=MAJORITY_CLAIM),
    ]


def unattributed_dissent_turn() -> list[dict]:
    """Missing participant_id: attribution must refuse, not silently drop."""
    turns = two_dissent_council()
    turns.append(
        {
            "turn_id": "t-r1-ghost",
            "round_index": 1,
            "participant_id": "",
            "role": "Ghost",
            "kind": "dissent",
            "is_dissent": True,
            "option_id": "opt-Z",
            "claim": "TOKEN-DSNT-GHOST: unattributed minority must not vanish",
        }
    )
    return turns


def sibling_council() -> list[dict]:
    """Second council whose dissent must remain reachable after parent aggregation."""
    return [
        _vote("q-chair", "opt-A", turn="t-q-chair", role="Chair", claim=MAJORITY_CLAIM),
        _vote("q-chair-2", "opt-A", turn="t-q-chair-2", role="Chair", claim=MAJORITY_CLAIM),
        _vote(
            "q-impossibility",
            "opt-D",
            turn="t-q-imp",
            role="Skeptic",
            is_dissent=True,
            kind="dissent",
            claim=TOKEN_GAMMA,
            rationale=TOKEN_GAMMA,
            evidence_cites=["e-fan-in"],
        ),
    ]


def kernel_events_for(turns: list[dict]) -> list[dict]:
    """Shape IMP-0264 kernel would emit; pipeline must not require a bypass write."""
    events = []
    for t in turns:
        events.append(
            {
                "event": "turn",
                "turn_id": t["turn_id"],
                "participant_id": t["participant_id"],
                "round_index": t.get("round_index", 0),
                "role": t.get("role", ""),
                "payload": {k: v for k, v in t.items()},
            }
        )
    return events
