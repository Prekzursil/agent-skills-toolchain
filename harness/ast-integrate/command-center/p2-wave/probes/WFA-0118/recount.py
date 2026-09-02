"""Independent bitmask recount of the seven certification conditions.

Does not import gate.py. Each condition is a bit; CERTIFIED iff the mask
equals the full seven-bit pattern. A sequential AND in gate.py that disagrees
with this mask is a split between two mechanisms, not a vote.
"""
from __future__ import annotations

from typing import Any

CONDITION_BITS = (
    "advantage_or_complement",
    "no_capability_loss",
    "one_control_plane",
    "lineage_decomposable",
    "licence_obligations_recorded",
    "gaming_detector_clear",
    "independent_review_pass",
)
FULL_MASK = (1 << len(CONDITION_BITS)) - 1
LICENCE_WEIGHT = {
    "AGPL-3.0": 40,
    "GPL-3.0": 30,
    "Apache-2.0": 20,
    "MIT": 10,
    "CC0-1.0": 0,
}


def _bit(index: int, held: bool) -> int:
    return (1 << index) if held else 0


def _advantage_held(packet: dict[str, Any]) -> bool:
    mp = packet.get("matched_pair") or {}
    scores = mp.get("source_scores") or {}
    if not scores:
        return False
    try:
        fusion = float(mp["fusion_score"])
        floor = float(mp["variance_floor"])
        comp = float(mp.get("complementarity_delta") or 0.0)
        best = max(float(v) for v in scores.values())
    except (KeyError, TypeError, ValueError):
        return False
    if floor < 0:
        return False
    delta = fusion - best
    return delta > floor or comp > 0


def _capability_held(packet: dict[str, Any]) -> bool:
    cap = packet.get("capability") or {}
    union = frozenset(str(x) for x in (cap.get("source_union") or []))
    have = frozenset(str(x) for x in (cap.get("fusion_set") or []))
    disconnected = tuple(str(x) for x in (cap.get("disconnected") or []))
    if not union:
        return False
    return union <= have and not disconnected


def _control_held(packet: dict[str, Any]) -> bool:
    cp = packet.get("control_plane") or {}
    try:
        return (
            int(cp["schedulers"]) == 1
            and int(cp["state_stores"]) == 1
            and int(cp["execution_order_owners"]) == 1
        )
    except (KeyError, TypeError, ValueError):
        return False


def _lineage_held(packet: dict[str, Any]) -> bool:
    lin = packet.get("lineage") or {}
    declared = tuple(sorted(str(x) for x in (packet.get("source_ids") or [])))
    recorded = tuple(sorted(str(x) for x in (lin.get("source_ids") or [])))
    decomp = tuple(sorted(str(x) for x in (lin.get("decomposition") or [])))
    roll = lin.get("rollback_rehearsal") or {}
    smoke = tuple(sorted(str(x) for x in (roll.get("smoke") or [])))
    return (
        declared == recorded == decomp == smoke
        and bool(roll.get("ok"))
        and bool(lin.get("operator"))
        and bool(declared)
    )


def _licence_held(packet: dict[str, Any]) -> bool:
    lic = packet.get("licence") or {}
    inherited = [str(x) for x in (lic.get("inherited") or [])]
    governing = str(lic.get("governing") or "")
    attribution = [str(x) for x in (lic.get("attribution") or [])]
    if not inherited or not attribution:
        return False
    weights = [LICENCE_WEIGHT.get(name) for name in inherited]
    if any(w is None for w in weights):
        return False
    strictest = max(inherited, key=lambda name: LICENCE_WEIGHT[name])
    return governing == strictest


def _gaming_held(packet: dict[str, Any]) -> bool:
    g = packet.get("gaming") or {}
    return (
        g.get("clear") is True
        and g.get("held_out_collapse") is False
        and not list(g.get("oracle_constants") or [])
        and g.get("test_mode_branch") is False
    )


def _review_held(packet: dict[str, Any]) -> bool:
    rev = packet.get("independent_review") or {}
    return str(rev.get("verdict") or "") == "PASS" and not rev.get("split")


_HOLD = (
    _advantage_held,
    _capability_held,
    _control_held,
    _lineage_held,
    _licence_held,
    _gaming_held,
    _review_held,
)


def mask_of(packet: dict[str, Any]) -> int:
    bits = 0
    for i, fn in enumerate(_HOLD):
        bits |= _bit(i, fn(packet))
    return bits


def recount(packet: dict[str, Any]) -> dict[str, Any]:
    mask = mask_of(packet)
    bits = []
    for i, name in enumerate(CONDITION_BITS):
        held = bool(mask & (1 << i))
        bits.append({"id": name, "bit": i, "held": held})
    certified = mask == FULL_MASK
    failed = [row["id"] for row in bits if not row["held"]]
    verdict = "CERTIFIED" if certified else "REFUSED"
    mp = packet.get("matched_pair") or {}
    scores = mp.get("source_scores") or {}
    if scores and not certified and not bits[0]["held"] and all(
        row["held"] for row in bits[1:]
    ):
        try:
            fusion = float(mp["fusion_score"])
            floor = float(mp["variance_floor"])
            best = max(float(v) for v in scores.values())
            delta = fusion - best
            comp = float(mp.get("complementarity_delta") or 0.0)
            if abs(delta) <= floor and comp <= 0:
                verdict = "INCONCLUSIVE"
        except (KeyError, TypeError, ValueError):
            pass
    return {
        "mechanism": "seven-bit-AND-mask",
        "mask": mask,
        "full_mask": FULL_MASK,
        "certified": certified,
        "verdict": verdict,
        "failed": failed,
        "bits": bits,
        "fusion_id": packet.get("fusion_id"),
    }
