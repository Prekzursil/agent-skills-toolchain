"""Participant-dominance detector: airtime OR surviving-claim concentration.

Shares are computed from the transcript. Synthesis.self_attestation is
read only as a diagnostic and never decides fired/silent. Surviving-claim
ownership is the seat that first uttered the claim id, not a synthesizer
attribution table (that table is a self-attestation by another name).

FIRE iff max_i(token_share_i) >= TAU or max_i(surviving_claim_share_i) >= TAU.
Turn share and evidence-cite share are reported, not fire channels: a
seat can be capped on turns and still own the outcome.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

PATHOLOGY = "participant-dominance-airtime-concentration"
TAU = 0.50
FIRE_RULE = "max(token_share, surviving_claim_share) >= tau"

_CONTROL_FIRED = False


def _turns(council: dict) -> list[dict]:
    transcript = council.get("transcript")
    if isinstance(transcript, dict) and transcript.get("turns"):
        return list(transcript["turns"])
    return list(council.get("turns") or [])


def _seats(council: dict) -> list[str]:
    seats = council.get("seats")
    if isinstance(seats, list) and seats:
        return [str(s) for s in seats]
    found: list[str] = []
    for turn in _turns(council):
        seat = str(turn.get("seat") or turn.get("speaker") or "")
        if seat and seat not in found:
            found.append(seat)
    return found


def _token_count(turn: dict) -> int:
    if turn.get("tokens") is not None:
        return int(turn["tokens"])
    text = str(turn.get("text") or "")
    return len(text.split())


def _claim_ids(turn: dict) -> list[str]:
    raw = turn.get("claims") or turn.get("claim_ids") or []
    if isinstance(raw, str):
        return [raw]
    return [str(c) for c in raw]


def first_utterance_owner(turns: list[dict]) -> dict[str, str]:
    """Map claim id -> seat of first utterance. Ignores synthesis.attribution."""
    owner: dict[str, str] = {}
    for turn in turns:
        seat = str(turn.get("seat") or turn.get("speaker") or "")
        for cid in _claim_ids(turn):
            if cid not in owner and seat:
                owner[cid] = seat
    return owner


def _accepted_claims(council: dict) -> list[str]:
    syn = council.get("synthesis") or {}
    raw = syn.get("accepted_claims") or syn.get("surviving_claims") or []
    return [str(c) for c in raw]


def _attestation(council: dict) -> dict[str, Any]:
    syn = council.get("synthesis") or {}
    att = syn.get("self_attestation") or syn.get("attestation") or {}
    return att if isinstance(att, dict) else {}


def shares(council: dict) -> dict[str, Any]:
    seats = _seats(council)
    turns = _turns(council)
    turn_n: dict[str, int] = {s: 0 for s in seats}
    token_n: dict[str, int] = {s: 0 for s in seats}
    cite_n: dict[str, int] = {s: 0 for s in seats}
    for turn in turns:
        seat = str(turn.get("seat") or turn.get("speaker") or "")
        if seat not in turn_n:
            turn_n[seat] = 0
            token_n[seat] = 0
            cite_n[seat] = 0
            if seat not in seats:
                seats.append(seat)
        turn_n[seat] += 1
        token_n[seat] += _token_count(turn)
        cites = turn.get("evidence_cites") or turn.get("evidence") or []
        cite_n[seat] += len(cites) if isinstance(cites, list) else 0

    owners = first_utterance_owner(turns)
    claim_n: dict[str, int] = {s: 0 for s in seats}
    accepted = _accepted_claims(council)
    attributed = 0
    for cid in accepted:
        owner = owners.get(cid)
        if owner is None:
            continue
        claim_n.setdefault(owner, 0)
        claim_n[owner] += 1
        attributed += 1

    def frac(counter: dict[str, int], total: int) -> dict[str, float | None]:
        if total <= 0:
            return {s: None for s in seats}
        return {s: counter.get(s, 0) / total for s in seats}

    token_total = sum(token_n.values())
    turn_total = sum(turn_n.values())
    cite_total = sum(cite_n.values())
    return {
        "seats": seats,
        "turn_share": frac(turn_n, turn_total),
        "token_share": frac(token_n, token_total),
        "surviving_claim_share": frac(claim_n, attributed),
        "evidence_cite_share": frac(cite_n, cite_total),
        "counts": {
            "turns": turn_n,
            "tokens": token_n,
            "surviving_claims": claim_n,
            "evidence_cites": cite_n,
            "accepted_attributed": attributed,
            "accepted_listed": len(accepted),
            "token_total": token_total,
            "turn_total": turn_total,
        },
        "claim_owners_from_transcript": owners,
    }


def _max_named(fracs: dict[str, float | None]) -> tuple[str | None, float | None]:
    best_seat = None
    best: float | None = None
    for seat, val in fracs.items():
        if val is None:
            continue
        if best is None or val > best:
            best, best_seat = val, seat
    return best_seat, best


def detect(council: dict, tau: float = TAU) -> dict[str, Any]:
    snap = shares(council)
    reasons: list[dict[str, Any]] = []
    for metric in ("token_share", "surviving_claim_share"):
        fracs = snap[metric]
        for seat, val in fracs.items():
            if val is not None and val >= tau:
                reasons.append(
                    {
                        "metric": metric,
                        "seat": seat,
                        "share": round(val, 6),
                        "rule": FIRE_RULE,
                    }
                )
    fired = bool(reasons)
    tok_seat, tok_max = _max_named(snap["token_share"])
    cl_seat, cl_max = _max_named(snap["surviving_claim_share"])
    att = _attestation(council)
    claimed_balanced = att.get("balanced")
    if claimed_balanced is None:
        claimed_balanced = att.get("no_dominance")
    dominant = None
    if fired:
        if (tok_max or 0) >= (cl_max or 0):
            dominant = tok_seat
        else:
            dominant = cl_seat
    return {
        "pathology": PATHOLOGY,
        "fired": fired,
        "silent": not fired,
        "tau": tau,
        "fire_rule": FIRE_RULE,
        "dominant_seat": dominant,
        "max_token_share": None if tok_max is None else round(tok_max, 6),
        "max_surviving_claim_share": None if cl_max is None else round(cl_max, 6),
        "token_leader": tok_seat,
        "claim_leader": cl_seat,
        "reasons": reasons,
        "shares": {
            "turn_share": snap["turn_share"],
            "token_share": snap["token_share"],
            "surviving_claim_share": snap["surviving_claim_share"],
            "evidence_cite_share": snap["evidence_cite_share"],
        },
        "counts": snap["counts"],
        "ignored_synthesizer_self_attestation": True,
        "synthesizer_claimed_balanced": claimed_balanced,
        "fixture_id": council.get("id"),
    }


def detect_known_present(council: dict, tau: float = TAU) -> dict[str, Any]:
    global _CONTROL_FIRED
    result = detect(council, tau=tau)
    result["detector_control_known_present"] = True
    if result["fired"]:
        _CONTROL_FIRED = True
    return result


def detect_after_control(council: dict, tau: float = TAU) -> dict[str, Any]:
    if not _CONTROL_FIRED:
        raise RuntimeError(
            "detector-control: refusing to report absence before a known-present "
            "instance has fired in this process"
        )
    return detect(council, tau=tau)


def reset_control() -> None:
    global _CONTROL_FIRED
    _CONTROL_FIRED = False


def throttle(council: dict, cap_share: float | None = None) -> dict:
    """Drop later turns of the token-leader until that seat's share <= 1/n.

    Post-throttle share is measured against the new total, so
    d_keep <= cap/(1-cap) * tokens_of_others.
    """
    out = deepcopy(council)
    seats = _seats(out)
    n = max(len(seats), 1)
    cap = (1.0 / n) if cap_share is None else cap_share
    turns = _turns(out)
    snap = shares(out)
    leader, tmax = _max_named(snap["token_share"])
    if leader is None or tmax is None or tmax <= cap:
        out["throttle"] = {"applied": False, "reason": "already-at-or-under-cap"}
        return out
    others = sum(
        _token_count(t)
        for t in turns
        if str(t.get("seat") or t.get("speaker")) != leader
    )
    if cap >= 1.0:
        max_keep = float(sum(_token_count(t) for t in turns))
    elif others <= 0:
        max_keep = 0.0
    else:
        max_keep = cap / (1.0 - cap) * others
    kept: list[dict] = []
    kept_dom = 0.0
    dropped = 0
    for turn in turns:
        seat = str(turn.get("seat") or turn.get("speaker") or "")
        if seat != leader:
            kept.append(turn)
            continue
        tok = _token_count(turn)
        if kept_dom + tok <= max_keep + 1e-9:
            kept.append(turn)
            kept_dom += tok
        else:
            dropped += 1
    out["turns"] = kept
    if isinstance(out.get("transcript"), dict):
        out["transcript"] = dict(out["transcript"])
        out["transcript"]["turns"] = kept
    remaining_accepted = []
    owners = first_utterance_owner(kept)
    for cid in _accepted_claims(out):
        if cid in owners:
            remaining_accepted.append(cid)
    syn = dict(out.get("synthesis") or {})
    syn["accepted_claims"] = remaining_accepted
    syn["answer"] = decide_from_turns(kept)
    out["synthesis"] = syn
    out["throttle"] = {
        "applied": True,
        "capped_seat": leader,
        "cap_share": cap,
        "turns_dropped": dropped,
        "pre_token_share": tmax,
    }
    return out


def decide_from_turns(turns: list[dict]) -> str | None:
    """Token-weighted majority of proposed_answer. Tie -> lexicographically first."""
    weight: dict[str, int] = {}
    for turn in turns:
        ans = turn.get("proposed_answer")
        if not ans:
            continue
        weight[str(ans)] = weight.get(str(ans), 0) + _token_count(turn)
    if not weight:
        return None
    best_w = max(weight.values())
    winners = sorted(a for a, w in weight.items() if w == best_w)
    return winners[0]


def decide(council: dict) -> str | None:
    syn = council.get("synthesis") or {}
    if syn.get("answer"):
        return str(syn["answer"])
    return decide_from_turns(_turns(council))


def quality(council: dict) -> dict[str, Any]:
    gold = council.get("gold_answer")
    got = decide(council)
    ok = gold is not None and got == gold
    return {
        "gold": gold,
        "got": got,
        "correct": bool(ok),
        "score": 1 if ok else 0,
    }


def false_positive_rate(results: list[dict]) -> dict[str, Any]:
    n = len(results)
    if n < 1:
        raise ValueError("false_positive_rate requires at least one clean fixture")
    fires = [r for r in results if r.get("fired")]
    return {
        "value": len(fires) / n,
        "numerator": len(fires),
        "denominator": n,
        "fired_ids": [r.get("fixture_id") for r in fires],
        "fixture_ids": [r.get("fixture_id") for r in results],
    }
