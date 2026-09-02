"""Independent recount of TST-0276 ledgers (does not call run_session / _tally)."""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping

from engagement import (
    DEFAULT_BUDGET,
    PROTOCOL_CONSENT_NO_OBJECTION,
    PROTOCOL_EXPLICIT_BALLOT,
    is_substantive,
)


def recount(spec: Mapping[str, Any]) -> dict[str, Any]:
    """Recompute engagement, escalation, and the consensus figure from acts."""
    acts = list(spec.get("acts") or [])
    roster = list(spec.get("roster") or [])
    n_rounds = int(spec.get("rounds") or 0)
    protocol = str(spec.get("protocol") or PROTOCOL_EXPLICIT_BALLOT)
    window = int(spec.get("objection_window_round") or n_rounds)
    budget = dict(DEFAULT_BUDGET)
    budget.update(spec.get("budget") or {})
    min_acts = int(budget["min_substantive_acts"])
    max_idle = int(budget["max_consecutive_inactive_rounds"])

    by_seat: dict[str, list[Mapping[str, Any]]] = {s: [] for s in roster}
    for act in acts:
        sid = str(act.get("seat_id") or "")
        by_seat.setdefault(sid, []).append(act)
        if sid not in roster:
            roster.append(sid)

    seats: dict[str, dict[str, Any]] = {}
    for sid in roster:
        seat_acts = by_seat.get(sid, [])
        subst = [a for a in seat_acts if is_substantive(a)]
        by_round: dict[int, list[Mapping[str, Any]]] = defaultdict(list)
        for a in seat_acts:
            by_round[int(a.get("round") or 0)].append(a)
        streak = 0
        longest = 0
        for r in range(1, n_rounds + 1):
            if any(is_substantive(a) for a in by_round[r]):
                streak = 0
            else:
                streak += 1
                longest = max(longest, streak)
        engaged = len(subst) >= min_acts
        idle_fire = longest > max_idle or (n_rounds > 0 and not engaged)
        status = "ENGAGED" if engaged and not idle_fire else "ABSENT"
        ballots = [
            str(a.get("ballot")).lower()
            for a in seat_acts
            if str(a.get("kind") or "").lower() == "vote" and a.get("ballot") not in (None, "")
        ]
        objected = any(
            str(a.get("kind") or "").lower() == "object" and is_substantive(a) for a in seat_acts
        )
        seats[sid] = {
            "status": status,
            "last_ballot": ballots[-1] if ballots else None,
            "objected": objected,
            "idle": longest,
            "substantive": len(subst),
        }

    engaged_ids = [s for s in roster if seats[s]["status"] == "ENGAGED"]
    absent_ids = [s for s in roster if seats[s]["status"] != "ENGAGED"]
    agree: list[str] = []
    roles: dict[str, str] = {}
    for sid in engaged_ids:
        ballot = seats[sid]["last_ballot"]
        if protocol == PROTOCOL_EXPLICIT_BALLOT:
            if ballot in {"yes", "aye", "for", "consent"}:
                agree.append(sid)
                roles[sid] = "AGREE"
            elif ballot in {"no", "nay", "against", "dissent"}:
                roles[sid] = "DISAGREE"
            else:
                roles[sid] = "ABSTAIN"
        else:
            if seats[sid]["objected"] or ballot in {"no", "nay", "against", "dissent"}:
                roles[sid] = "OBJECTED" if seats[sid]["objected"] else "DISAGREE"
            elif ballot in {"yes", "aye", "for", "consent"}:
                agree.append(sid)
                roles[sid] = "AGREE"
            else:
                window_acts = [
                    a
                    for a in by_seat[sid]
                    if int(a.get("round") or 0) == window
                ]
                silent = not any(
                    str(a.get("kind") or "").lower() in {"object", "vote"} and is_substantive(a)
                    for a in window_acts
                )
                if silent:
                    agree.append(sid)
                    roles[sid] = "NO_OBJECTION"
                else:
                    roles[sid] = "ABSTAIN"
    for sid in absent_ids:
        roles[sid] = "ABSENT"
    denom = len(engaged_ids)
    numer = len(agree)
    return {
        "protocol": protocol,
        "engaged": engaged_ids,
        "absent": absent_ids,
        "agree": agree,
        "roles": roles,
        "numerator": numer,
        "denominator": denom,
        "figure": (numer / denom) if denom else None,
        "escalation_fires": bool(absent_ids),
        "inactivity_fires": any(seats[s]["idle"] > max_idle or seats[s]["status"] == "ABSENT" for s in roster),
        "ghost_counted_as_agreeing": "ghost" in agree,
    }
