#!/usr/bin/env python3
"""WFA-0093 repair-versus-rebuild cost gate.

The cost RULE is a frozen dict, hashed, and recorded before any candidate is
scored. Dual-path spikes are an independent measurement: they are not an input
to v1. A spike that prefers the path v1 did not choose falsifies v1 and forces
a revision that re-runs every verdict.

A flip to CLEAN-ROOM-REIMPLEMENT or REBUILD-FROM-SPEC must copy the source
licence and provenance records. Dropping either is a gate failure, not a
completed clean-room.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"

# Written BEFORE apply. Changing these constants changes rule_hash and is a
# new rule version. Do not "tune" after reading verdicts.
RULE: dict[str, Any] = {
    "id": "WFA-0093-repair-vs-rebuild-v1",
    "version": 1,
    "written_before_apply": True,
    "formula": (
        "repair_cost = 3*defects_reproduced + 8*runtime_coupling + 7*licence_friction; "
        "rebuild_cost = 20 - 5*spec_completeness + 2*max(0, hours-2); "
        "hours is estimated_rebuild_hours under v1"
    ),
    "weights": {
        "defect": 3,
        "coupling": 8,
        "licence": 7,
        "rebuild_base": 20,
        "spec_credit": 5,
        "hour_weight": 2,
        "hour_floor": 2,
    },
    "flip_predicate": "repair_cost > rebuild_cost",
    "flip_to_rebuild_from_spec_if": "spec_completeness >= 2",
    "else_flip_to": "CLEAN-ROOM-REIMPLEMENT",
    "keep": "REPAIR",
    "near_threshold_abs": 3,
    "falsifier": (
        "For a near-threshold candidate, if the cheaper measured spike path "
        "(repair vs rebuild) disagrees with the path implied by the v1 "
        "verdict, v1 is false. Revise: substitute measured rebuild_path_hours "
        "for estimated hours on spiked rows, re-run every verdict."
    ),
    "licence_rule": (
        "A flip must copy licence and provenance from the source candidate. "
        "Clean-room does not erase attribution."
    ),
}

DISPOSITIONS = (
    "REPAIR",
    "CLEAN-ROOM-REIMPLEMENT",
    "REBUILD-FROM-SPEC",
)


def rule_hash(rule: dict[str, Any] | None = None) -> str:
    payload = json.dumps(rule or RULE, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_candidates(path: Path | None = None) -> list[dict[str, Any]]:
    p = path or (FIX / "repair_candidates.json")
    doc = json.loads(p.read_text(encoding="utf-8"))
    rows = doc.get("candidates") or []
    if len(rows) != 15:
        raise ValueError(f"expected 15 REPAIR candidates, got {len(rows)}")
    for row in rows:
        if row.get("classification") != "REPAIR":
            raise ValueError(f"{row.get('id')} is not REPAIR")
    return rows


def load_spikes(path: Path | None = None) -> list[dict[str, Any]]:
    p = path or (FIX / "spike_results.json")
    doc = json.loads(p.read_text(encoding="utf-8"))
    spikes = doc.get("spikes") or []
    if len(spikes) < 2:
        raise ValueError("need two near-threshold dual-path spikes")
    return spikes


def repair_cost(candidate: dict[str, Any], rule: dict[str, Any] | None = None) -> int:
    w = (rule or RULE)["weights"]
    return (
        w["defect"] * int(candidate["defects_reproduced"])
        + w["coupling"] * int(candidate["runtime_coupling"])
        + w["licence"] * int(candidate["licence_friction"])
    )


def rebuild_cost(
    candidate: dict[str, Any],
    *,
    hours: int | None = None,
    rule: dict[str, Any] | None = None,
) -> int:
    w = (rule or RULE)["weights"]
    h = int(candidate["estimated_rebuild_hours"] if hours is None else hours)
    return (
        w["rebuild_base"]
        - w["spec_credit"] * int(candidate["spec_completeness"])
        + w["hour_weight"] * max(0, h - w["hour_floor"])
    )


def choose_disposition(candidate: dict[str, Any], rcost: int, bcost: int) -> str:
    if rcost <= bcost:
        return "REPAIR"
    if int(candidate["spec_completeness"]) >= 2:
        return "REBUILD-FROM-SPEC"
    return "CLEAN-ROOM-REIMPLEMENT"


def score_one(
    candidate: dict[str, Any],
    *,
    hours: int | None = None,
    rule: dict[str, Any] | None = None,
    hashed: str | None = None,
) -> dict[str, Any]:
    rule = rule or RULE
    rcost = repair_cost(candidate, rule)
    bcost = rebuild_cost(candidate, hours=hours, rule=rule)
    disp = choose_disposition(candidate, rcost, bcost)
    flipped = disp != "REPAIR"
    near = abs(rcost - bcost) <= int(rule["near_threshold_abs"])
    return {
        "id": candidate["id"],
        "prior_classification": candidate["classification"],
        "inputs": {
            "defects_reproduced": candidate["defects_reproduced"],
            "runtime_coupling": candidate["runtime_coupling"],
            "licence_friction": candidate["licence_friction"],
            "spec_completeness": candidate["spec_completeness"],
            "hours_used": int(
                candidate["estimated_rebuild_hours"] if hours is None else hours
            ),
            "hours_source": "estimate" if hours is None else "spike-measured",
        },
        "repair_cost": rcost,
        "rebuild_cost": bcost,
        "delta": rcost - bcost,
        "near_threshold": near,
        "disposition": disp,
        "flipped": flipped,
        "rule_id": rule["id"],
        "rule_hash": hashed or rule_hash(rule),
        "licence": copy.deepcopy(candidate["licence"]),
        "provenance": copy.deepcopy(candidate["provenance"]),
        "attribution_preserved": True,
    }


def apply_rule(
    candidates: list[dict[str, Any]],
    *,
    spike_hours: dict[str, int] | None = None,
    rule: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Score every candidate. spike_hours, if given, is the v2 substitution."""
    rule = rule or RULE
    hashed = rule_hash(rule)
    if not rule.get("written_before_apply"):
        raise ValueError("rule must be marked written_before_apply before apply")
    hours_map = spike_hours or {}
    out = []
    for cand in candidates:
        hours = hours_map.get(cand["id"])
        out.append(score_one(cand, hours=hours, rule=rule, hashed=hashed))
    return out


def implied_path(disposition: str) -> str:
    return "repair" if disposition == "REPAIR" else "rebuild"


def spike_contradictions(
    decisions: list[dict[str, Any]], spikes: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Independent check: measured cheaper path vs v1-implied path."""
    by_id = {d["id"]: d for d in decisions}
    hits = []
    for spike in spikes:
        cid = spike["candidate_id"]
        if cid not in by_id:
            raise KeyError(f"spike for unknown candidate {cid}")
        measured = spike["cheaper_measured_path"]
        implied = implied_path(by_id[cid]["disposition"])
        if measured != implied:
            hits.append(
                {
                    "candidate_id": cid,
                    "v1_disposition": by_id[cid]["disposition"],
                    "v1_implied_path": implied,
                    "measured_cheaper_path": measured,
                    "repair_path_hours": spike["repair_path_hours"],
                    "rebuild_path_hours": spike["rebuild_path_hours"],
                }
            )
    return hits


def revise_with_spikes(
    candidates: list[dict[str, Any]],
    spikes: list[dict[str, Any]],
    *,
    rule: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """v2: measured rebuild hours replace estimates on spiked rows; re-run all."""
    hours = {s["candidate_id"]: int(s["rebuild_path_hours"]) for s in spikes}
    rule_v2 = copy.deepcopy(rule or RULE)
    rule_v2["id"] = "WFA-0093-repair-vs-rebuild-v2-spike-hours"
    rule_v2["version"] = 2
    rule_v2["formula"] = (
        "same weights as v1; hours is rebuild_path_hours when a spike exists, "
        "else estimated_rebuild_hours"
    )
    decisions = apply_rule(candidates, spike_hours=hours, rule=rule_v2)
    meta = {
        "from_rule": (rule or RULE)["id"],
        "to_rule": rule_v2["id"],
        "to_hash": rule_hash(rule_v2),
        "substituted_hours": hours,
        "reason": "spike cheaper-path disagreed with v1; re-ran every verdict",
    }
    return decisions, meta


def attribution_ok(source: dict[str, Any], decision: dict[str, Any]) -> bool:
    if decision.get("licence") != source.get("licence"):
        return False
    if decision.get("provenance") != source.get("provenance"):
        return False
    lic = source.get("licence") or {}
    prov = source.get("provenance") or {}
    if not lic.get("spdx") or not lic.get("source"):
        return False
    if not prov.get("anchor") or not prov.get("record_id"):
        return False
    if prov.get("record_id") != source.get("id"):
        return False
    if decision.get("flipped") and decision.get("attribution_preserved") is not True:
        return False
    return True


def drop_provenance(decision: dict[str, Any]) -> dict[str, Any]:
    """Planted mutant: flip without keeping provenance (must be rejected)."""
    mutant = copy.deepcopy(decision)
    mutant["provenance"] = None
    mutant["attribution_preserved"] = False
    return mutant


def histogram(decisions: list[dict[str, Any]]) -> dict[str, int]:
    counts = {k: 0 for k in DISPOSITIONS}
    for d in decisions:
        counts[d["disposition"]] += 1
    return counts


def run_gate(
    candidates: list[dict[str, Any]] | None = None,
    spikes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    cands = candidates if candidates is not None else load_candidates()
    sp = spikes if spikes is not None else load_spikes()
    hashed = rule_hash(RULE)
    v1 = apply_rule(cands, rule=RULE)
    contradictions = spike_contradictions(v1, sp)
    revisions: list[dict[str, Any]] = []
    final = v1
    if contradictions:
        final, meta = revise_with_spikes(cands, sp, rule=RULE)
        meta["contradictions"] = contradictions
        revisions.append(meta)
    by_src = {c["id"]: c for c in cands}
    attr_fail = [d["id"] for d in final if not attribution_ok(by_src[d["id"]], d)]
    if attr_fail:
        raise ValueError(f"attribution lost on flip/keep: {attr_fail}")
    return {
        "rule": copy.deepcopy(RULE),
        "rule_hash": hashed,
        "decisions": final,
        "v1_decisions": v1,
        "histogram": histogram(final),
        "spikes": sp,
        "contradictions": contradictions,
        "revisions": revisions,
        "attribution_failures": attr_fail,
    }
