"""Fusion evidence packets for the WFA-0118 certification gate.

Each packet is the raw cited evidence a third party re-derives from.
Mutations flip exactly one of the seven gate conditions.
"""
from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

CONDITION_IDS = (
    "advantage_or_complement",
    "no_capability_loss",
    "one_control_plane",
    "lineage_decomposable",
    "licence_obligations_recorded",
    "gaming_detector_clear",
    "independent_review_pass",
)

LICENCE_RANK = {
    "AGPL-3.0": 40,
    "GPL-3.0": 30,
    "Apache-2.0": 20,
    "MIT": 10,
    "CC0-1.0": 0,
}


def canonical_dumps(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def packet_digest(packet: dict[str, Any]) -> str:
    raw = canonical_dumps(packet).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def known_good(*, fusion_id: str = "wf-fuse-alpha", n_stages: int = 3) -> dict[str, Any]:
    """Advantage above the variance floor; all six remaining conditions hold."""
    sources = ["wf-src-a", "wf-src-b"]
    caps = ["cap-parse", "cap-emit", "cap-verify"]
    return {
        "fusion_id": fusion_id,
        "source_ids": list(sources),
        "n_stages": int(n_stages),
        "matched_pair": {
            "fusion_score": 0.82,
            "source_scores": {"wf-src-a": 0.70, "wf-src-b": 0.68},
            "variance_floor": 0.04,
            "input_hash": "a" * 64,
            "complementarity_delta": 0.0,
        },
        "capability": {
            "source_union": list(caps),
            "fusion_set": list(caps),
            "disconnected": [],
        },
        "control_plane": {
            "schedulers": 1,
            "state_stores": 1,
            "execution_order_owners": 1,
            "helper_processes": 2,
        },
        "lineage": {
            "source_ids": list(sources),
            "operator": "compose",
            "parameters": {"order": list(sources)},
            "decomposition": list(sources),
            "rollback_rehearsal": {"ok": True, "smoke": list(sources)},
        },
        "licence": {
            "inherited": ["MIT", "Apache-2.0"],
            "governing": "Apache-2.0",
            "attribution": ["src-a-authors", "src-b-authors"],
        },
        "gaming": {
            "clear": True,
            "held_out_collapse": False,
            "oracle_constants": [],
            "test_mode_branch": False,
        },
        "independent_review": {
            "verdict": "PASS",
            "reviewer_id": "WFA-0117-cross-vendor",
            "split": False,
        },
    }


def known_good_complement(*, n_stages: int = 5) -> dict[str, Any]:
    """No advantage above the floor; measured complementarity delta carries the OR."""
    packet = known_good(fusion_id="wf-fuse-complement", n_stages=n_stages)
    packet["matched_pair"]["fusion_score"] = 0.71
    packet["matched_pair"]["complementarity_delta"] = 0.18
    return packet


def inconclusive_inside_floor() -> dict[str, Any]:
    """Advantage inside the floor and zero complementarity: not a pass."""
    packet = known_good(fusion_id="wf-fuse-inconclusive", n_stages=4)
    packet["matched_pair"]["fusion_score"] = 0.72
    packet["matched_pair"]["complementarity_delta"] = 0.0
    return packet


def mutate(base: dict[str, Any], condition_id: str) -> dict[str, Any]:
    """Flip exactly one of the seven conditions."""
    packet = copy.deepcopy(base)
    packet["fusion_id"] = f"{base['fusion_id']}-minus-{condition_id}"
    if condition_id == "advantage_or_complement":
        packet["matched_pair"]["fusion_score"] = 0.55
        packet["matched_pair"]["complementarity_delta"] = 0.0
    elif condition_id == "no_capability_loss":
        packet["capability"]["fusion_set"] = ["cap-parse", "cap-emit"]
        packet["capability"]["disconnected"] = ["cap-verify"]
    elif condition_id == "one_control_plane":
        packet["control_plane"]["schedulers"] = 2
    elif condition_id == "lineage_decomposable":
        packet["lineage"]["decomposition"] = ["wf-src-a"]
        packet["lineage"]["rollback_rehearsal"] = {"ok": False, "smoke": []}
    elif condition_id == "licence_obligations_recorded":
        packet["licence"]["inherited"] = []
        packet["licence"]["governing"] = ""
        packet["licence"]["attribution"] = []
    elif condition_id == "gaming_detector_clear":
        packet["gaming"]["clear"] = False
        packet["gaming"]["test_mode_branch"] = True
        packet["gaming"]["oracle_constants"] = ["EXPECTED_ORACLE_BYTES"]
    elif condition_id == "independent_review_pass":
        packet["independent_review"]["verdict"] = "REFUTED"
        packet["independent_review"]["split"] = True
    else:
        raise ValueError(f"unknown condition {condition_id!r}")
    return packet


def seven_negatives(base: dict[str, Any] | None = None) -> list[tuple[str, dict[str, Any]]]:
    seed = base or known_good()
    return [(cid, mutate(seed, cid)) for cid in CONDITION_IDS]


def stage_variants() -> list[tuple[str, dict[str, Any]]]:
    """Same decision must hold at n_stages=1 and n_stages=99."""
    good_lo = known_good(fusion_id="wf-fuse-alpha-s1", n_stages=1)
    good_hi = known_good(fusion_id="wf-fuse-alpha-s99", n_stages=99)
    bad_lo = mutate(known_good(fusion_id="wf-fuse-alpha", n_stages=1), "no_capability_loss")
    bad_hi = mutate(known_good(fusion_id="wf-fuse-alpha", n_stages=99), "no_capability_loss")
    return [
        ("good-s1", good_lo),
        ("good-s99", good_hi),
        ("lossy-s1", bad_lo),
        ("lossy-s99", bad_hi),
    ]


def all_named() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {
        "known-good-advantage": known_good(),
        "known-good-complement": known_good_complement(),
        "inconclusive-inside-floor": inconclusive_inside_floor(),
    }
    for cid, packet in seven_negatives():
        out[f"neg-{cid}"] = packet
    for name, packet in stage_variants():
        out[name] = packet
    return out
