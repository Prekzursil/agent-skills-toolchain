"""Feed claimed-expertise authorities into production resolve_weights."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
WEIGHTS = REPO / "tools/council/vote/weights.py"


def _weights_mod():
    spec = importlib.util.spec_from_file_location("adv0099_weights", WEIGHTS)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {WEIGHTS}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["adv0099_weights"] = mod
    spec.loader.exec_module(mod)
    return mod


def resolve_authorities(authorities: dict[str, int]) -> dict:
    W = _weights_mod()
    rows = [
        {
            "seat_id": sid,
            "authority": int(auth),
            "expertise": "cryptography",
            "expertise_basis": "free-text self-assertion",
        }
        for sid, auth in authorities.items()
    ]
    graph = W.graph_from_rows(rows)
    res = W.resolve_weights(graph)
    # Confirm extra keys on the mapping are ignored: rebuild via seat_from_mapping
    parsed = [W.seat_from_mapping(r) for r in rows]
    ignored_expertise = all(
        not hasattr(s, "expertise") or getattr(s, "expertise", None) in (None, "")
        for s in parsed
    )
    return {
        "effective": dict(res.effective),
        "conserved": bool(res.conserved),
        "total_before": res.total_power_before,
        "total_after": res.total_power_after,
        "expertise_field_ignored": ignored_expertise,
        "authority_used": {s.seat_id: s.authority for s in parsed},
    }


def run_weight_paths(calibration: dict) -> dict:
    naive = calibration["naive_authority_for_crypto_task"]
    gated = calibration["gated_authority_for_crypto_task"]
    naive_res = resolve_authorities(naive)
    gated_res = resolve_authorities(gated)
    claimed_naive = naive_res["effective"].get("claimed-crypto")
    claimed_gated = gated_res["effective"].get("claimed-crypto")
    genuine_gated = gated_res["effective"].get("genuine-crypto")
    return {
        "pass": (
            claimed_naive == 5
            and claimed_gated == 1
            and genuine_gated == 5
            and naive_res["expertise_field_ignored"]
            and naive_res["conserved"]
            and gated_res["conserved"]
        ),
        "naive": naive_res,
        "gated": gated_res,
        "unverifiable_claim_accepted_as_weight": claimed_naive == 5,
        "quiz_refuses_premium": claimed_gated == 1,
        "genuine_premium_kept": genuine_gated == 5,
        "production_ignores_expertise_field": naive_res["expertise_field_ignored"],
        "note": (
            "Production seat_from_mapping / resolve_weights accept the caller "
            "authority integer and ignore an expertise field. A hallucinated "
            "expert therefore receives the naive premium (5) as vote weight. "
            "The known-answer gate refuses that premium (1) and keeps it for "
            "the genuine cryptographer."
        ),
    }
