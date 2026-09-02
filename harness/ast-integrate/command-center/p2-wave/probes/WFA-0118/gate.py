"""Certification gate: emit CERTIFIED only when all seven conditions hold.

n_stages is recorded on the packet and never read here. A fusion with one
stage and a fusion with ninety-nine stages receive the same verdict for the
same seven-condition vector.
"""
from __future__ import annotations

from typing import Any

from packets import CONDITION_IDS, LICENCE_RANK

VERDICT_CERTIFIED = "CERTIFIED"
VERDICT_REFUSED = "REFUSED"
VERDICT_INCONCLUSIVE = "INCONCLUSIVE"


def _pass(reason: str) -> dict[str, str]:
    return {"result": "PASS", "reason": reason}


def _fail(reason: str) -> dict[str, str]:
    return {"result": "FAIL", "reason": reason}


def check_advantage_or_complement(packet: dict[str, Any]) -> dict[str, str]:
    mp = packet.get("matched_pair") or {}
    scores = mp.get("source_scores") or {}
    if not scores:
        return _fail("no-source-scores")
    try:
        fusion = float(mp["fusion_score"])
        floor = float(mp["variance_floor"])
        comp = float(mp.get("complementarity_delta") or 0.0)
        best = max(float(v) for v in scores.values())
    except (KeyError, TypeError, ValueError):
        return _fail("matched-pair-unreadable")
    if floor < 0:
        return _fail("negative-variance-floor")
    delta = fusion - best
    if delta > floor:
        return _pass(f"advantage={delta:.4f}>floor={floor:.4f}")
    if comp > 0:
        return _pass(f"complementarity_delta={comp:.4f}")
    if abs(delta) <= floor:
        return _fail(f"inconclusive_inside_floor delta={delta:.4f} floor={floor:.4f}")
    return _fail(f"worse_than_sources delta={delta:.4f}")


def check_no_capability_loss(packet: dict[str, Any]) -> dict[str, str]:
    cap = packet.get("capability") or {}
    union = {str(x) for x in (cap.get("source_union") or [])}
    have = {str(x) for x in (cap.get("fusion_set") or [])}
    disconnected = [str(x) for x in (cap.get("disconnected") or [])]
    lost = sorted(union - have)
    if lost or disconnected:
        return _fail(f"lost={lost} disconnected={disconnected}")
    if not union:
        return _fail("empty-source-union")
    return _pass("fusion_superset_of_source_union")


def check_one_control_plane(packet: dict[str, Any]) -> dict[str, str]:
    cp = packet.get("control_plane") or {}
    try:
        schedulers = int(cp["schedulers"])
        stores = int(cp["state_stores"])
        owners = int(cp["execution_order_owners"])
    except (KeyError, TypeError, ValueError):
        return _fail("control-plane-unreadable")
    helpers = int(cp.get("helper_processes") or 0)
    if schedulers == 1 and stores == 1 and owners == 1:
        return _pass(f"singular-control helpers={helpers}")
    return _fail(f"duplicate-control schedulers={schedulers} stores={stores} owners={owners}")


def check_lineage_decomposable(packet: dict[str, Any]) -> dict[str, str]:
    lin = packet.get("lineage") or {}
    declared = [str(x) for x in (packet.get("source_ids") or [])]
    recorded = [str(x) for x in (lin.get("source_ids") or [])]
    decomp = [str(x) for x in (lin.get("decomposition") or [])]
    roll = lin.get("rollback_rehearsal") or {}
    if sorted(declared) != sorted(recorded):
        return _fail("lineage-source-mismatch")
    if sorted(decomp) != sorted(declared):
        return _fail(f"decomposition={decomp} != sources={declared}")
    if not roll.get("ok"):
        return _fail("rollback-rehearsal-failed")
    smoke = [str(x) for x in (roll.get("smoke") or [])]
    if sorted(smoke) != sorted(declared):
        return _fail("rollback-smoke-incomplete")
    if not lin.get("operator"):
        return _fail("operator-missing")
    return _pass("decomposition-matches-and-rollback-green")


def check_licence_obligations_recorded(packet: dict[str, Any]) -> dict[str, str]:
    lic = packet.get("licence") or {}
    inherited = [str(x) for x in (lic.get("inherited") or [])]
    governing = str(lic.get("governing") or "")
    attribution = [str(x) for x in (lic.get("attribution") or [])]
    if not inherited:
        return _fail("inherited-licences-empty")
    if not attribution:
        return _fail("attribution-lost")
    ranked = [LICENCE_RANK.get(name) for name in inherited]
    if any(r is None for r in ranked):
        return _fail(f"unknown-licence-in {inherited}")
    strictest = max(inherited, key=lambda name: LICENCE_RANK[name])
    if governing != strictest:
        return _fail(f"governing={governing!r} != strictest={strictest!r}")
    return _pass(f"governing={governing}")


def check_gaming_detector_clear(packet: dict[str, Any]) -> dict[str, str]:
    g = packet.get("gaming") or {}
    constants = list(g.get("oracle_constants") or [])
    if g.get("clear") is True and g.get("held_out_collapse") is False and not constants and g.get("test_mode_branch") is False:
        return _pass("gaming-clear")
    return _fail(
        "gaming-detected "
        f"clear={g.get('clear')} collapse={g.get('held_out_collapse')} "
        f"constants={constants} test_mode={g.get('test_mode_branch')}"
    )


def check_independent_review_pass(packet: dict[str, Any]) -> dict[str, str]:
    rev = packet.get("independent_review") or {}
    if str(rev.get("verdict") or "") == "PASS" and not rev.get("split"):
        return _pass(f"reviewer={rev.get('reviewer_id')}")
    return _fail(f"review-not-pass verdict={rev.get('verdict')} split={rev.get('split')}")


_CHECKERS = {
    "advantage_or_complement": check_advantage_or_complement,
    "no_capability_loss": check_no_capability_loss,
    "one_control_plane": check_one_control_plane,
    "lineage_decomposable": check_lineage_decomposable,
    "licence_obligations_recorded": check_licence_obligations_recorded,
    "gaming_detector_clear": check_gaming_detector_clear,
    "independent_review_pass": check_independent_review_pass,
}


def evaluate(packet: dict[str, Any]) -> dict[str, Any]:
    """Sequential AND over the seven named conditions. Fusion depth is not an input."""
    conditions = []
    all_pass = True
    inconclusive = False
    for cid in CONDITION_IDS:
        row = dict(_CHECKERS[cid](packet))
        row["id"] = cid
        conditions.append(row)
        if row["result"] != "PASS":
            all_pass = False
            if cid == "advantage_or_complement" and str(row["reason"]).startswith(
                "inconclusive_inside_floor"
            ):
                inconclusive = True
    if all_pass:
        verdict = VERDICT_CERTIFIED
    elif inconclusive and all(c["result"] == "PASS" for c in conditions if c["id"] != "advantage_or_complement"):
        verdict = VERDICT_INCONCLUSIVE
    else:
        verdict = VERDICT_REFUSED
    failed = [c["id"] for c in conditions if c["result"] != "PASS"]
    return {
        "fusion_id": packet.get("fusion_id"),
        "source_ids": list(packet.get("source_ids") or []),
        "certified": verdict == VERDICT_CERTIFIED,
        "verdict": verdict,
        "conditions": conditions,
        "failed": failed,
        "fusion_stage_count_ignored": True,
    }


def certify_or_refuse(packet: dict[str, Any]) -> dict[str, Any]:
    return evaluate(packet)
