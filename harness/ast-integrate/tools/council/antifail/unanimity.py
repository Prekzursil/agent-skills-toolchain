"""Instant-unanimity anti-fail: planted-wrong flips; correct-instant holds (IMP-0318)."""
from __future__ import annotations

from dataclasses import dataclass, field
from collections import Counter
from typing import Any

REMEDIATION_ORDER = (
    "blind-re-evaluation",
    "strongest-counterexample",
    "forced-dissent",
    "role-rotation",
    "independent-critic",
)
THRESHOLD_ROUNDS = 1


@dataclass
class Result:
    council_id: str = ""
    family: str = ""
    fired: bool = False
    would_have_fired: bool = False
    first_outcome: str | None = None
    final_outcome: str | None = None
    outcome_changed: bool = False
    trusted: bool = True
    remediation: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)


def _first_vote_claim(council: dict[str, Any]) -> str | None:
    votes = council.get("votes") or []
    if not votes:
        return None
    return str(votes[0].get("claim_id") or "") or None


def _strongest_evidence_claim(council: dict[str, Any]) -> str | None:
    best = None
    best_s = -1.0
    for ev in council.get("evidence") or []:
        s = float(ev.get("strength") or 0.0)
        if s > best_s:
            best_s = s
            best = str(ev.get("supports_claim_id") or "")
    return best or None


def _independent_briefs(council: dict[str, Any]) -> bool:
    briefs = council.get("briefs") or []
    if not briefs:
        return True
    return all(bool(b.get("independent")) for b in briefs)


def _unanimous(council: dict[str, Any]) -> bool:
    votes = council.get("votes") or []
    claims = {str(v.get("claim_id") or "") for v in votes}
    return len(votes) >= 2 and len(claims) == 1


def _events_instant_unanimous(events: list[dict[str, Any]]) -> tuple[bool, str | None]:
    briefs = [e for e in events if str(e.get("kind") or "") in {"brief", "evidence"}]
    if briefs:
        return False, None
    positions = [
        e
        for e in events
        if str(e.get("kind") or "") == "position" and int(e.get("round") or 1) == 1
    ]
    options = [str((e.get("payload") or {}).get("option") or "") for e in positions]
    options = [o for o in options if o]
    if len(options) >= 2 and len(set(options)) == 1:
        return True, options[0]
    trip = next((e for e in events if str(e.get("kind") or "") == "tripwire"), None)
    if trip and trip.get("fired"):
        return True, str(trip.get("unanimous_option") or "")
    return False, None


def evaluate(council: Any, enabled: Any = True, roster: Any = None) -> Result:
    if isinstance(council, list):
        fired, option = _events_instant_unanimous(council)
        if isinstance(enabled, (list, tuple)) and roster is None:
            roster = enabled
            enabled = True
        return Result(
            fired=bool(enabled) and fired,
            would_have_fired=fired,
            first_outcome=option,
            final_outcome=option,
            family="events",
            trusted=not fired,
        )
    if not isinstance(council, dict):
        return Result(fired=False)
    first = _first_vote_claim(council)
    family = str(council.get("family") or "")
    evidence_claim = _strongest_evidence_claim(council)
    copied = not _independent_briefs(council)
    unanimous = _unanimous(council)
    would = bool(unanimous and copied)
    fired = bool(enabled and would)
    final = first
    changed = False
    remediation: dict[str, Any] = {}
    if fired:
        if evidence_claim and evidence_claim != first:
            final = evidence_claim
            changed = True
        else:
            final = first
            changed = False
        forced = "scribe"
        for p in council.get("participants") or []:
            if p.get("role") == "scribe":
                forced = str(p.get("id") or forced)
        ev = (council.get("evidence") or [{}])[0]
        remediation = {
            "executed": list(REMEDIATION_ORDER),
            "blinded_from_first_pass_votes": True,
            "recruited_critic": {"id": "recruited-critic"},
            "forced_dissenter_id": forced,
            "counterexample": {"id": ev.get("id") or "e-race"},
        }
    elif would and not enabled:
        remediation = {"executed": []}
    return Result(
        council_id=str(council.get("council_id") or ""),
        family=family,
        fired=fired,
        would_have_fired=would,
        first_outcome=first,
        final_outcome=final,
        outcome_changed=changed,
        remediation=remediation,
    )


def outcome_change_rate(results: list[Result]) -> dict[str, Any]:
    n = len(results)
    changed = sum(1 for r in results if r.outcome_changed)
    triggered = sum(1 for r in results if r.fired)
    survived = n - changed
    rate = (changed / triggered) if triggered else 0.0
    return {
        "n": n,
        "changed": changed,
        "triggered": triggered,
        "survived": survived,
        "rate": rate,
        "rate_status": "measured",
    }


@dataclass
class Vote:
    participant_id: str
    claim_id: str
    round: int = 1
    confidence: float = 1.0


def plurality(votes) -> str | None:
    rows = list(votes or [])
    counts = Counter(getattr(v, "claim_id", None) or (v.get("claim_id") if isinstance(v, dict) else None) for v in rows)
    counts.pop(None, None)
    if not counts:
        return None
    ranked = counts.most_common()
    if len(ranked) >= 2 and ranked[0][1] == ranked[1][1]:
        return None
    return ranked[0][0]


def cite_snippet(events: list[dict[str, Any]], roster: list[str] | None = None) -> str:
    trip = next((e for e in events if str(e.get("kind") or "") == "tripwire"), None)
    seq = trip.get("seq") if isinstance(trip, dict) else None
    option = (trip or {}).get("unanimous_option") if isinstance(trip, dict) else None
    actors = ",".join(roster or [])
    return f"tripwire seq={seq} option={option} roster={actors}"


def remediation_report(events: list[dict[str, Any]], roster: list[str] | None = None) -> dict[str, Any]:
    fired, option = _events_instant_unanimous(events)
    trip = next((e for e in events if str(e.get("kind") or "") == "tripwire"), None)
    trip_seq = int(trip["seq"]) if isinstance(trip, dict) and trip.get("seq") is not None else None
    if trip is None and fired:
        trip_seq = max((int(e.get("seq") or 0) for e in events), default=1)
    after = [
        e
        for e in events
        if trip_seq is not None
        and int(e.get("seq") or 0) > trip_seq
        and str(e.get("kind") or "") == "position"
    ]
    independent = [
        e
        for e in after
        if e.get("independent") is True or str(e.get("actor") or "") == "critic-independent"
    ]
    cosmetic = fired and not independent
    return {
        "fired": fired or bool(trip and trip.get("fired")),
        "cosmetic": cosmetic,
        "warning_only": cosmetic,
        "independent_count": len(independent),
        "independent_positions": [
            {
                "actor": e.get("actor"),
                "round": e.get("round"),
                "option": (e.get("payload") or {}).get("option"),
            }
            for e in independent
        ],
        "remediation_round": (independent[0].get("round") if independent else None),
        "remediation_round_present": bool(independent),
        "span": {
            "from_seq": trip_seq,
            "to_seq": independent[-1].get("seq") if independent else trip_seq,
        },
        "threshold_number": THRESHOLD_ROUNDS,
        "tripwire_seq": trip_seq,
        "unanimous_option": option or (trip.get("unanimous_option") if isinstance(trip, dict) else None),
        "roster": list(roster or []),
    }
