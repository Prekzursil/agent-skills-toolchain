"""CNL-0025 chair-capture bound: two independent channels.

Channel 1 (seat-share excess): recognition mass per position_id versus the
fraction of floor-requesting seats that hold that position. Excess above
EXCESS_LIMIT is moderator capture of airtime.

Channel 2 (synthesis coverage): every submitted position_id must appear in
synthesis.cited_position_ids. A missing id is capture of the record by the
chair who writes or approves the synthesis.

The chair is CAPTURED if either channel fires. An even-handed chair (round-
robin seats, full citation coverage) is SILENT on both.

These channels are different mechanisms: arithmetic on counts vs set
difference on ids. Neither reads the other.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

LIMIT_ID = "CAPTURE-BOUND-DUAL"
EXCESS_LIMIT = 0.20


def _requesters(session: dict) -> list[dict]:
    return [
        p
        for p in (session.get("participants") or [])
        if isinstance(p, dict) and p.get("requested_floor") is True
    ]


def seat_shares(session: dict) -> dict[str, float]:
    req = _requesters(session)
    n = len(req)
    if n == 0:
        return {}
    counts: Counter[str] = Counter(str(p.get("position_id") or "") for p in req)
    counts.pop("", None)
    return {pid: c / n for pid, c in counts.items()}


def recognition_shares(session: dict) -> dict[str, float]:
    req = {str(p.get("id")): str(p.get("position_id") or "") for p in _requesters(session)}
    recs = [str(x) for x in (session.get("recognitions") or [])]
    pos_counts: Counter[str] = Counter()
    for pid in recs:
        pos = req.get(pid)
        if pos:
            pos_counts[pos] += 1
    total = sum(pos_counts.values())
    if total <= 0:
        return {k: 0.0 for k in seat_shares(session)}
    shares = {k: 0.0 for k in seat_shares(session)}
    for pos, c in pos_counts.items():
        shares[pos] = c / total
    return shares


def recognition_excess(session: dict) -> dict[str, Any]:
    seats = seat_shares(session)
    recs = recognition_shares(session)
    excess = {pos: recs.get(pos, 0.0) - seats.get(pos, 0.0) for pos in seats}
    worst_pos = max(excess, key=excess.get) if excess else None
    worst = excess.get(worst_pos, 0.0) if worst_pos else 0.0
    fires = worst > EXCESS_LIMIT
    return {
        "channel": "seat-share-excess",
        "limit_id": LIMIT_ID,
        "excess_limit": EXCESS_LIMIT,
        "seat_shares": seats,
        "recognition_shares": recs,
        "excess": excess,
        "worst_position_id": worst_pos,
        "worst_excess": worst,
        "fires": fires,
        "silent": not fires,
    }


def synthesis_coverage(session: dict) -> dict[str, Any]:
    submitted = sorted(
        {
            str(p.get("position_id") or "")
            for p in (session.get("participants") or [])
            if isinstance(p, dict) and p.get("position_id")
        }
    )
    syn = session.get("synthesis") if isinstance(session.get("synthesis"), dict) else {}
    cited = sorted({str(x) for x in (syn.get("cited_position_ids") or []) if x})
    missing = sorted(set(submitted) - set(cited))
    extra = sorted(set(cited) - set(submitted))
    fires = bool(missing)
    return {
        "channel": "synthesis-coverage",
        "limit_id": LIMIT_ID,
        "submitted_position_ids": submitted,
        "cited_position_ids": cited,
        "missing_position_ids": missing,
        "extra_position_ids": extra,
        "fires": fires,
        "silent": not fires,
    }


def detect(session: dict) -> dict[str, Any]:
    req = _requesters(session)
    positions = {str(p.get("position_id") or "") for p in req}
    positions.discard("")
    applicable = len(req) >= 2 and len(positions) >= 2
    rec = recognition_excess(session)
    cov = synthesis_coverage(session)
    captured = bool(applicable and (rec["fires"] or cov["fires"]))
    return {
        "limit_id": LIMIT_ID,
        "applicable": applicable,
        "requester_count": len(req),
        "position_count": len(positions),
        "captured": captured,
        "silent": (not captured) if applicable else False,
        "inapplicable_reason": (
            None
            if applicable
            else "need >=2 floor-requesting seats and >=2 distinct position_ids"
        ),
        "recognition": rec,
        "coverage": cov,
        "channels_fired": [c for c, row in (("recognition", rec), ("coverage", cov)) if row["fires"]],
    }
