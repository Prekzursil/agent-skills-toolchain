"""Scripted council transcripts. Votes use 1-based round; TURN events use 0-based round_index."""
from __future__ import annotations

from typing import Any


def _turn(seq: int, round_index: int, turn_index: int, pid: str, output: str) -> dict[str, Any]:
    return {
        "seq": seq,
        "kind": "TURN",
        "round_index": round_index,
        "turn_index": turn_index,
        "participant_id": pid,
        "status": "ok",
        "output": output,
        "obligations": ["position"],
        "obligations_met": ["position"],
        "obligations_missing": [],
        "elapsed_ms": 40 + turn_index,
    }


def _round_events(start_seq: int, round_index: int, roster: list[str], texts: dict[str, str]) -> list[dict[str, Any]]:
    events = [
        {
            "seq": start_seq,
            "kind": "ROUND_BEGIN",
            "round_index": round_index,
            "turn_index": None,
            "participant_id": None,
            "status": None,
            "output": None,
            "obligations": [],
            "obligations_met": [],
            "obligations_missing": [],
            "elapsed_ms": None,
        }
    ]
    seq = start_seq + 1
    for i, pid in enumerate(roster, start=1):
        events.append(_turn(seq, round_index, i, pid, texts[pid]))
        seq += 1
    events.append(
        {
            "seq": seq,
            "kind": "ROUND_END",
            "round_index": round_index,
            "turn_index": None,
            "participant_id": None,
            "status": None,
            "output": None,
            "obligations": [],
            "obligations_met": [],
            "obligations_missing": [],
            "elapsed_ms": None,
        }
    )
    return events


ROSTER = ["architect", "pragmatist", "critic", "skeptic"]
CLAIM_SHIP = "ship-anyway"
CLAIM_HOLD = "require-invalidation"


def healthy() -> dict[str, Any]:
    """Disagreement in round 1, independent update in round 2, every seat stays."""
    r1_text = {
        "architect": "ship-anyway",
        "pragmatist": "ship-anyway",
        "critic": "ship-anyway",
        "skeptic": "require-invalidation",
    }
    r2_text = {p: "require-invalidation" for p in ROSTER}
    events = _round_events(1, 0, ROSTER, r1_text)
    events.extend(_round_events(len(events) + 1, 1, ROSTER, r2_text))
    events.append(
        {
            "seq": len(events) + 1,
            "kind": "COUNCIL_END",
            "round_index": None,
            "turn_index": None,
            "participant_id": None,
            "status": None,
            "output": None,
            "obligations": [],
            "obligations_met": [],
            "obligations_missing": [],
            "elapsed_ms": None,
        }
    )
    votes = [
        {"participant_id": "architect", "claim_id": CLAIM_SHIP, "round": 1, "confidence": 0.7},
        {"participant_id": "pragmatist", "claim_id": CLAIM_SHIP, "round": 1, "confidence": 0.6},
        {"participant_id": "critic", "claim_id": CLAIM_SHIP, "round": 1, "confidence": 0.6},
        {"participant_id": "skeptic", "claim_id": CLAIM_HOLD, "round": 1, "confidence": 0.9},
        {"participant_id": "architect", "claim_id": CLAIM_HOLD, "round": 2, "confidence": 0.8},
        {"participant_id": "pragmatist", "claim_id": CLAIM_HOLD, "round": 2, "confidence": 0.8},
        {"participant_id": "critic", "claim_id": CLAIM_HOLD, "round": 2, "confidence": 0.85},
        {"participant_id": "skeptic", "claim_id": CLAIM_HOLD, "round": 2, "confidence": 0.9},
    ]
    briefs = [
        {
            "participant_id": p,
            "text": "independent brief",
            "evidence_ids": ["e-race"],
            "independent": True,
        }
        for p in ROSTER
    ]
    return {
        "id": "healthy",
        "expect_pathological": False,
        "expect_fired": [],
        "rounds_elapsed": 2,
        "disagreement_rounds": 1,
        "events": events,
        "votes": votes,
        "briefs": briefs,
    }


def instant_unanimity() -> dict[str, Any]:
    """Round-1 unanimous, no disagreement round — premature-closure detector."""
    text = {p: CLAIM_SHIP for p in ROSTER}
    events = _round_events(1, 0, ROSTER, text)
    events.append(
        {
            "seq": len(events) + 1,
            "kind": "COUNCIL_END",
            "round_index": None,
            "turn_index": None,
            "participant_id": None,
            "status": None,
            "output": None,
            "obligations": [],
            "obligations_met": [],
            "obligations_missing": [],
            "elapsed_ms": None,
        }
    )
    votes = [
        {"participant_id": p, "claim_id": CLAIM_SHIP, "round": 1, "confidence": 0.9}
        for p in ROSTER
    ]
    briefs = [
        {
            "participant_id": p,
            "text": "same sentence as everyone else",
            "evidence_ids": [],
            "independent": False,
        }
        for p in ROSTER
    ]
    return {
        "id": "instant_unanimity",
        "expect_pathological": True,
        "expect_fired": ["premature_closure_instant_unanimity"],
        "rounds_elapsed": 1,
        "disagreement_rounds": 0,
        "events": events,
        "votes": votes,
        "briefs": briefs,
    }


def seat_drop() -> dict[str, Any]:
    """Skeptic is a minority in round 1 and has no TURN in round 2."""
    r1_text = {
        "architect": CLAIM_SHIP,
        "pragmatist": CLAIM_SHIP,
        "critic": CLAIM_SHIP,
        "skeptic": CLAIM_HOLD,
    }
    continuing = ["architect", "pragmatist", "critic"]
    r2_text = {p: CLAIM_SHIP for p in continuing}
    events = _round_events(1, 0, ROSTER, r1_text)
    events.extend(_round_events(len(events) + 1, 1, continuing, r2_text))
    events.append(
        {
            "seq": len(events) + 1,
            "kind": "COUNCIL_END",
            "round_index": None,
            "turn_index": None,
            "participant_id": None,
            "status": None,
            "output": None,
            "obligations": [],
            "obligations_met": [],
            "obligations_missing": [],
            "elapsed_ms": None,
        }
    )
    votes = [
        {"participant_id": "architect", "claim_id": CLAIM_SHIP, "round": 1, "confidence": 0.7},
        {"participant_id": "pragmatist", "claim_id": CLAIM_SHIP, "round": 1, "confidence": 0.7},
        {"participant_id": "critic", "claim_id": CLAIM_SHIP, "round": 1, "confidence": 0.7},
        {"participant_id": "skeptic", "claim_id": CLAIM_HOLD, "round": 1, "confidence": 0.9},
        {"participant_id": "architect", "claim_id": CLAIM_SHIP, "round": 2, "confidence": 0.8},
        {"participant_id": "pragmatist", "claim_id": CLAIM_SHIP, "round": 2, "confidence": 0.8},
        {"participant_id": "critic", "claim_id": CLAIM_SHIP, "round": 2, "confidence": 0.8},
    ]
    briefs = [
        {
            "participant_id": p,
            "text": "majority brief",
            "evidence_ids": [],
            "independent": False,
        }
        for p in continuing
    ]
    return {
        "id": "seat_drop",
        "expect_pathological": True,
        "expect_fired": ["dissent_suppression_seat_drop"],
        "rounds_elapsed": 2,
        "disagreement_rounds": 1,
        "events": events,
        "votes": votes,
        "briefs": briefs,
    }


def vote_collapse() -> dict[str, Any]:
    """Skeptic flips onto the majority with Brief.independent false; still present."""
    r1_text = {
        "architect": CLAIM_SHIP,
        "pragmatist": CLAIM_SHIP,
        "critic": CLAIM_SHIP,
        "skeptic": CLAIM_HOLD,
    }
    r2_text = {p: CLAIM_SHIP for p in ROSTER}
    events = _round_events(1, 0, ROSTER, r1_text)
    events.extend(_round_events(len(events) + 1, 1, ROSTER, r2_text))
    events.append(
        {
            "seq": len(events) + 1,
            "kind": "COUNCIL_END",
            "round_index": None,
            "turn_index": None,
            "participant_id": None,
            "status": None,
            "output": None,
            "obligations": [],
            "obligations_met": [],
            "obligations_missing": [],
            "elapsed_ms": None,
        }
    )
    votes = [
        {"participant_id": "architect", "claim_id": CLAIM_SHIP, "round": 1, "confidence": 0.7},
        {"participant_id": "pragmatist", "claim_id": CLAIM_SHIP, "round": 1, "confidence": 0.7},
        {"participant_id": "critic", "claim_id": CLAIM_SHIP, "round": 1, "confidence": 0.7},
        {"participant_id": "skeptic", "claim_id": CLAIM_HOLD, "round": 1, "confidence": 0.9},
        {"participant_id": "architect", "claim_id": CLAIM_SHIP, "round": 2, "confidence": 0.8},
        {"participant_id": "pragmatist", "claim_id": CLAIM_SHIP, "round": 2, "confidence": 0.8},
        {"participant_id": "critic", "claim_id": CLAIM_SHIP, "round": 2, "confidence": 0.8},
        {"participant_id": "skeptic", "claim_id": CLAIM_SHIP, "round": 2, "confidence": 0.5},
    ]
    briefs = [
        {
            "participant_id": p,
            "text": "not an independent brief",
            "evidence_ids": [],
            "independent": False,
        }
        for p in ROSTER
    ]
    return {
        "id": "vote_collapse",
        "expect_pathological": True,
        "expect_fired": ["dissent_suppression_vote_collapse"],
        "rounds_elapsed": 2,
        "disagreement_rounds": 1,
        "events": events,
        "votes": votes,
        "briefs": briefs,
    }


def all_fixtures() -> list[dict[str, Any]]:
    return [healthy(), instant_unanimity(), seat_drop(), vote_collapse()]
