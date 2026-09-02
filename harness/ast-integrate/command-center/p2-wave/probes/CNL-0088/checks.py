"""Shared both-states, FP, sweep, and throttle measurements for CNL-0088."""
from __future__ import annotations

import json
from typing import Any

import detector as D
import fixtures as F

P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0088/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0088/probe2_throttle_quality.py"
)


def compact(result: dict) -> str:
    slim = {
        "fixture_id": result.get("fixture_id"),
        "fired": result.get("fired"),
        "silent": result.get("silent"),
        "tau": result.get("tau"),
        "max_token_share": result.get("max_token_share"),
        "max_surviving_claim_share": result.get("max_surviving_claim_share"),
        "dominant_seat": result.get("dominant_seat"),
        "reasons": result.get("reasons"),
        "ignored_synthesizer_self_attestation": result.get(
            "ignored_synthesizer_self_attestation"
        ),
        "synthesizer_claimed_balanced": result.get("synthesizer_claimed_balanced"),
    }
    return json.dumps(slim, sort_keys=True, separators=(",", ":"))


def both_states() -> dict[str, Any]:
    D.reset_control()
    present = D.detect_known_present(F.known_present_control())
    if not present["fired"]:
        raise RuntimeError("detector-control did not fire on known-present fixture")
    planted = D.detect(F.planted_bad_airtime())
    claims = D.detect(F.planted_bad_claims_only())
    good = D.detect_after_control(F.known_good_balanced())
    wolf = D.detect(F.attestation_cries_wolf())
    prolific = D.detect(F.prolific_not_dominant())
    return {
        "detector_control": present,
        "planted_airtime": planted,
        "planted_claims": claims,
        "known_good": good,
        "attestation_wolf": wolf,
        "prolific": prolific,
    }


def fp_bundle() -> dict[str, Any]:
    results = []
    for doc in F.fp_suite():
        r = D.detect(doc)
        r["fixture_id"] = doc["id"]
        results.append(r)
    rate = D.false_positive_rate(results)
    return {"rate": rate, "results": results}


def independent_max_shares(council: dict) -> dict[str, float | None]:
    """Second mechanism: recompute max shares from raw turns, not detect().fired."""
    turns = council.get("turns") or []
    tokens: dict[str, int] = {}
    first: dict[str, str] = {}
    for turn in turns:
        seat = str(turn.get("seat") or "")
        tokens[seat] = tokens.get(seat, 0) + int(turn.get("tokens") or 0)
        for cid in turn.get("claims") or []:
            if cid not in first and seat:
                first[str(cid)] = seat
    tok_total = sum(tokens.values())
    accepted = list((council.get("synthesis") or {}).get("accepted_claims") or [])
    claims: dict[str, int] = {}
    attributed = 0
    for cid in accepted:
        owner = first.get(str(cid))
        if owner is None:
            continue
        claims[owner] = claims.get(owner, 0) + 1
        attributed += 1
    max_tok = (max(tokens.values()) / tok_total) if tok_total else None
    max_cl = (max(claims.values()) / attributed) if attributed else None
    return {"max_token_share": max_tok, "max_surviving_claim_share": max_cl}


def token_sweep() -> list[dict[str, Any]]:
    rows = []
    for share in (0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.70, 0.80):
        doc = F.token_concentrated(share)
        r = D.detect(doc)
        rows.append(
            {
                "target_share": share,
                "fixture_id": doc["id"],
                "max_token_share": r["max_token_share"],
                "fired": r["fired"],
            }
        )
    return rows


def claim_sweep() -> list[dict[str, Any]]:
    rows = []
    for k in (2, 3, 4, 5, 6):
        doc = F.claim_concentrated(k)
        r = D.detect(doc)
        rows.append(
            {
                "k_loud": k,
                "n_claims": 8,
                "fixture_id": doc["id"],
                "max_surviving_claim_share": r["max_surviving_claim_share"],
                "max_token_share": r["max_token_share"],
                "fired": r["fired"],
            }
        )
    return rows


def first_fire(rows: list[dict], key: str) -> dict[str, Any] | None:
    for row in rows:
        if row.get("fired"):
            return row
    return None


def throttle_quality() -> dict[str, Any]:
    wrong = F.quality_wrong_dominant()
    expert = F.quality_expert_dominant()
    w_before = D.quality(wrong)
    w_after = D.quality(D.throttle(wrong))
    e_before = D.quality(expert)
    e_th = D.throttle(expert)
    e_after = D.quality(e_th)
    return {
        "wrong_dominant": {
            "before": w_before,
            "after": w_after,
            "improved": w_after["score"] > w_before["score"],
        },
        "expert_dominant": {
            "before": e_before,
            "after": e_after,
            "degraded": e_after["score"] < e_before["score"],
            "throttle": e_th.get("throttle"),
        },
        "quality_monotonic": False,
    }


def assert_both_states(bundle: dict) -> list[str]:
    errors = []
    if not bundle["detector_control"]["fired"]:
        errors.append("detector-control silent on known-present")
    if not bundle["planted_airtime"]["fired"]:
        errors.append("planted-bad-airtime silent")
    if not bundle["planted_claims"]["fired"]:
        errors.append("planted-bad-claims-only silent")
    if bundle["known_good"]["fired"]:
        errors.append("known-good-balanced fired")
    if bundle["attestation_wolf"]["fired"]:
        errors.append("attestation-cries-wolf fired (self-attestation leaked)")
    if bundle["prolific"]["fired"]:
        errors.append("prolific-not-dominant-0.40 fired")
    planted = bundle["planted_airtime"]
    if planted.get("synthesizer_claimed_balanced") is not True:
        errors.append("planted-bad fixture lost lying attestation")
    if planted.get("ignored_synthesizer_self_attestation") is not True:
        errors.append("detector did not ignore synthesizer self-attestation")
    claims = bundle["planted_claims"]
    if (claims.get("max_token_share") or 1) >= D.TAU:
        errors.append("claims-only fixture is not even on tokens")
    if (claims.get("max_surviving_claim_share") or 0) < D.TAU:
        errors.append("claims-only fixture did not concentrate surviving claims")
    return errors
