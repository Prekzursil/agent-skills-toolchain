"""Groupthink detectors that read only named, existing transcript fields.

Portable detectors (each field is in the live inventory from fields.py):

  premature_closure_instant_unanimity
      votes.round, votes.claim_id, votes.participant_id,
      rounds_elapsed, disagreement_rounds
  dissent_suppression_seat_drop
      votes.round, votes.claim_id, votes.participant_id,
      events.kind, events.participant_id, events.round_index
  dissent_suppression_vote_collapse
      votes.round, votes.claim_id, votes.participant_id,
      briefs.participant_id, briefs.independent

Not portable (propose() returns portable=False):

  asch_critical_trial_conformity_rate
      private_judgment, trial_type, ground_truth — none exist.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Iterable

from fields import field_exists, inventory

# Named paths used by portable detectors. Probe 1 asserts each is in inventory.
PREMATURE_CLOSURE_FIELDS = (
    "votes.round",
    "votes.claim_id",
    "votes.participant_id",
    "rounds_elapsed",
    "disagreement_rounds",
)
SEAT_DROP_FIELDS = (
    "votes.round",
    "votes.claim_id",
    "votes.participant_id",
    "events.kind",
    "events.participant_id",
    "events.round_index",
)
VOTE_COLLAPSE_FIELDS = (
    "votes.round",
    "votes.claim_id",
    "votes.participant_id",
    "briefs.participant_id",
    "briefs.independent",
)
ASCH_FIELDS = (
    "private_judgment",
    "trial_type",
    "ground_truth",
)

DETECTORS = (
    {
        "id": "premature_closure_instant_unanimity",
        "classical_measure": "premature-closure timing (operationalized as round-1 unanimity)",
        "transcript_fields": list(PREMATURE_CLOSURE_FIELDS),
        "portable": True,
        "reads": (
            "All Vote.claim_id values in round 1, Vote.participant_id count, "
            "CouncilSnapshot.rounds_elapsed, CouncilSnapshot.disagreement_rounds."
        ),
        "fires_when": (
            "rounds_elapsed <= 1 AND disagreement_rounds == 0 AND at least two "
            "round-1 votes exist AND they all share one claim_id."
        ),
    },
    {
        "id": "dissent_suppression_seat_drop",
        "classical_measure": "dissent-suppression / mindguard (seat disappearance)",
        "transcript_fields": list(SEAT_DROP_FIELDS),
        "portable": True,
        "reads": (
            "Minority Vote.participant_id in round r versus TURN events at "
            "round_index r-1 and r."
        ),
        "fires_when": (
            "A participant whose round-r vote is not the majority claim has a "
            "TURN in that round and zero TURNs in round r+1 while at least one "
            "other participant still has a TURN (council continued without them)."
        ),
    },
    {
        "id": "dissent_suppression_vote_collapse",
        "classical_measure": "dissent-suppression / self-censorship (public flip)",
        "transcript_fields": list(VOTE_COLLAPSE_FIELDS),
        "portable": True,
        "reads": (
            "Vote.claim_id across consecutive rounds plus Brief.independent "
            "for the flipping seat."
        ),
        "fires_when": (
            "A seat moves from a non-majority claim_id to the next-round "
            "majority AND their Brief.independent is false (no independent "
            "re-evaluation recorded)."
        ),
    },
)

NOT_PORTABLE = (
    {
        "id": "asch_critical_trial_conformity_rate",
        "classical_measure": "Asch-style critical-trial conformity rate",
        "requested_fields": list(ASCH_FIELDS),
        "portable": False,
        "reason": (
            "Asch's 36.8% figure is the share of *public* answers that matched "
            "a unanimous *wrong* majority on *critical* trials, scored against "
            "a known correct line length, with a no-majority control baseline "
            "(<1% error). Computing it requires a private_judgment distinct "
            "from the public Vote.claim_id, a trial_type (critical vs neutral), "
            "and a ground_truth. None of those names exist on kernel "
            "Event.as_dict, Vote.to_dict, the chair journal, or "
            "council-audit participant_action_logs. Public agreement "
            "(share of Vote.claim_id) is consensus_pct, not Asch conformity."
        ),
    },
    {
        "id": "janis_eight_symptom_checklist",
        "classical_measure": "Janis groupthink 8-symptom inventory as a scored detector",
        "requested_fields": [
            "morale",
            "illusion_of_invulnerability",
            "belief_in_inherent_morality",
        ],
        "portable": False,
        "reason": (
            "Janis (1972) is a qualitative symptom list, not a numeric "
            "timing or error rate. Symptoms such as illusion of invulnerability "
            "and belief in inherent morality have no named transcript field. "
            "Inventing a minute-cutoff or a 36.8% copy on agent panels would "
            "be an E3 headline without a baseline on this population."
        ),
    },
)


def propose(
    detector_id: str,
    transcript_fields: Iterable[str],
    inv: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Accept a detector only when every named field exists."""
    data = inv if inv is not None else inventory()
    fields = [str(f) for f in transcript_fields]
    missing = [f for f in fields if not field_exists(f, data)]
    return {
        "id": detector_id,
        "transcript_fields": fields,
        "missing_fields": missing,
        "portable": len(missing) == 0 and len(fields) > 0,
    }


def _majority_claim(votes: list[dict[str, Any]], round_no: int) -> str | None:
    ids = [str(v.get("claim_id") or "") for v in votes if int(v.get("round") or 0) == round_no]
    ids = [i for i in ids if i]
    if len(ids) < 2:
        return None
    claim, n = Counter(ids).most_common(1)[0]
    if n <= len(ids) / 2:
        return None
    return claim


def premature_closure_instant_unanimity(transcript: dict[str, Any]) -> dict[str, Any]:
    votes = list(transcript.get("votes") or [])
    rounds_elapsed = int(transcript.get("rounds_elapsed") or 0)
    disagreement_rounds = int(transcript.get("disagreement_rounds") or 0)
    r1 = [v for v in votes if int(v.get("round") or 0) == 1]
    claims = [str(v.get("claim_id") or "") for v in r1]
    claims = [c for c in claims if c]
    fired = (
        rounds_elapsed <= 1
        and disagreement_rounds == 0
        and len(claims) >= 2
        and len(set(claims)) == 1
    )
    return {
        "detector": "premature_closure_instant_unanimity",
        "fired": fired,
        "n_round1_votes": len(claims),
        "distinct_claim_ids": sorted(set(claims)),
        "rounds_elapsed": rounds_elapsed,
        "disagreement_rounds": disagreement_rounds,
    }


def _event_round_index(event: dict[str, Any]) -> int | None:
    # Kernel round_index is 0-based. `or -1` would map 0 to -1.
    raw = event.get("round_index")
    if raw is None:
        return None
    return int(raw)


def dissent_suppression_seat_drop(transcript: dict[str, Any]) -> dict[str, Any]:
    votes = list(transcript.get("votes") or [])
    events = [
        e
        for e in (transcript.get("events") or [])
        if str(e.get("kind") or "") == "TURN"
    ]
    dropped: list[str] = []
    rounds = sorted({int(v.get("round") or 0) for v in votes if int(v.get("round") or 0) > 0})
    hit_round = None
    for r in rounds:
        maj = _majority_claim(votes, r)
        if not maj:
            continue
        minority = [
            str(v.get("participant_id") or "")
            for v in votes
            if int(v.get("round") or 0) == r and str(v.get("claim_id") or "") != maj
        ]
        minority = [p for p in minority if p]
        ev_now = {
            str(e.get("participant_id") or "")
            for e in events
            if _event_round_index(e) == r - 1
        }
        ev_next = {
            str(e.get("participant_id") or "")
            for e in events
            if _event_round_index(e) == r
        }
        if not ev_next:
            continue
        newly = [p for p in minority if p in ev_now and p not in ev_next]
        if newly:
            dropped = newly
            hit_round = r
            break
    return {
        "detector": "dissent_suppression_seat_drop",
        "fired": bool(dropped),
        "dropped_participant_ids": dropped,
        "round": hit_round,
    }


def dissent_suppression_vote_collapse(transcript: dict[str, Any]) -> dict[str, Any]:
    votes = list(transcript.get("votes") or [])
    briefs = list(transcript.get("briefs") or [])
    independent = {
        str(b.get("participant_id") or ""): bool(b.get("independent")) for b in briefs
    }
    by: dict[str, dict[int, str]] = {}
    for v in votes:
        pid = str(v.get("participant_id") or "")
        r = int(v.get("round") or 0)
        cid = str(v.get("claim_id") or "")
        if pid and r and cid:
            by.setdefault(pid, {})[r] = cid
    rounds = sorted({int(v.get("round") or 0) for v in votes if int(v.get("round") or 0) > 0})
    collapsed: list[str] = []
    for r, r2 in zip(rounds, rounds[1:]):
        maj1 = _majority_claim(votes, r)
        maj2 = _majority_claim(votes, r2)
        if not maj1 or not maj2:
            continue
        for pid, hist in by.items():
            if r not in hist or r2 not in hist:
                continue
            if hist[r] != maj1 and hist[r2] == maj2 and hist[r] != hist[r2]:
                if independent.get(pid, False) is False:
                    collapsed.append(pid)
    return {
        "detector": "dissent_suppression_vote_collapse",
        "fired": bool(collapsed),
        "collapsed_participant_ids": sorted(set(collapsed)),
    }


RUNNERS = {
    "premature_closure_instant_unanimity": premature_closure_instant_unanimity,
    "dissent_suppression_seat_drop": dissent_suppression_seat_drop,
    "dissent_suppression_vote_collapse": dissent_suppression_vote_collapse,
}


def run_all(transcript: dict[str, Any]) -> dict[str, Any]:
    rows = [fn(transcript) for fn in RUNNERS.values()]
    fired = [r["detector"] for r in rows if r["fired"]]
    pathological = bool(fired)
    return {
        "rows": rows,
        "fired": fired,
        "pathological": pathological,
        "threshold": (
            "PATHALOGICAL if any portable detector fires: instant round-1 "
            "unanimity, minority seat-drop while the council continues, or "
            "non-independent vote collapse onto the next majority. This is an "
            "operational flag for this transcript, not Asch's 36.8% and not a "
            "validated clinical cutoff on LLM panels."
        ),
    }


def portable_catalog(inv: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    data = inv if inv is not None else inventory()
    out = []
    for spec in DETECTORS:
        proposal = propose(spec["id"], spec["transcript_fields"], data)
        row = dict(spec)
        row["missing_fields"] = proposal["missing_fields"]
        row["field_exists"] = {
            f: field_exists(f, data) for f in spec["transcript_fields"]
        }
        row["portable"] = proposal["portable"]
        out.append(row)
    return out


def not_portable_catalog(inv: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    data = inv if inv is not None else inventory()
    out = []
    for spec in NOT_PORTABLE:
        proposal = propose(spec["id"], spec["requested_fields"], data)
        row = dict(spec)
        row["missing_fields"] = proposal["missing_fields"]
        row["field_exists"] = {
            f: field_exists(f, data) for f in spec["requested_fields"]
        }
        row["portable"] = False
        out.append(row)
    return out
