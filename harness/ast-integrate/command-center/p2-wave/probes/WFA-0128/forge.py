#!/usr/bin/env python3
"""Reference interpreter for the WFA-0128 workflow-forge meta-workflow.

This is a decision procedure, not a fusion generator. Both terminals are valid:

  CERTIFIED-FUSION — fusion beats the best source by the margin floor, keeps
                     every source capability, has one control plane, decomposes
                     to its sources, and passes rollback rehearsal
  NO-IMPROVEMENT   — names the best source and a numeric margin; includes the
                     known-bad-fusion control (mechanism / control-plane conflict)

The seven named operators are the construction surface. Policy selects among
them from measured pair properties. An illegal pair is never constructed.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
MARGIN_FLOOR = 0.05
OPERATORS = (
    "stage-splice",
    "common-core",
    "union",
    "best-of-breed",
    "conditional-hybrid",
    "ensemble",
    "progressive",
)
MECHANISM_CONFLICTS = frozenset(
    {
        frozenset({"scheduler.central", "scheduler.distributed"}),
        frozenset({"store.single-writer", "store.sharded"}),
        frozenset({"auth.session-cookie", "auth.mtls-only"}),
    }
)
LICENCE_INCOMPAT = frozenset({frozenset({"GPL-3.0", "proprietary"})})
W_QUALITY = 0.40
W_COVERAGE = 0.30
W_RECOVERY = 0.20
W_USABILITY = 0.10
USABILITY_STAGE_SOFT_CAP = 6


def _sha(obj: Any) -> str:
    blob = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def quality(wf: dict) -> float:
    return _mean([float(s["score"]) for s in wf.get("stages") or []])


def coverage(wf: dict, goal: dict) -> float:
    required = list(goal.get("required_mechanisms") or [])
    if not required:
        return 0.0
    have = set(wf.get("mechanisms") or [])
    return len(have.intersection(required)) / len(required)


def usability(wf: dict) -> float:
    n = len(wf.get("stages") or [])
    return max(0.0, 1.0 - 0.05 * max(0, n - USABILITY_STAGE_SOFT_CAP))


def recovery(wf: dict) -> float:
    return 1.0 if wf.get("has_rollback") else 0.5


def score(wf: dict, goal: dict) -> float:
    return (
        W_QUALITY * quality(wf)
        + W_COVERAGE * coverage(wf, goal)
        + W_RECOVERY * recovery(wf)
        + W_USABILITY * usability(wf)
    )


def jaccard(a: dict, b: dict) -> float:
    sa, sb = set(a.get("mechanisms") or []), set(b.get("mechanisms") or [])
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def mechanism_conflicts(a: dict, b: dict) -> list[tuple[str, str]]:
    hits: list[tuple[str, str]] = []
    ma, mb = set(a.get("mechanisms") or []), set(b.get("mechanisms") or [])
    for x in ma:
        for y in mb:
            if frozenset({x, y}) in MECHANISM_CONFLICTS:
                hits.append((x, y))
    return sorted(hits)


def licence_conflicts(a: dict, b: dict) -> list[tuple[str, str]]:
    pair = frozenset({str(a.get("licence") or ""), str(b.get("licence") or "")})
    if pair in LICENCE_INCOMPAT:
        return [tuple(sorted(pair))]  # type: ignore[return-value]
    return []


def control_plane_conflict(a: dict, b: dict) -> bool:
    ca, cb = a.get("control_plane"), b.get("control_plane")
    return bool(ca and cb and ca != cb)


def preconditions(a: dict, b: dict) -> dict:
    mech = mechanism_conflicts(a, b)
    lic = licence_conflicts(a, b)
    two_planes = control_plane_conflict(a, b)
    reasons: list[str] = []
    if mech:
        reasons.append("MECHANISM_CONFLICT:" + ",".join(f"{x}|{y}" for x, y in mech))
    if lic:
        reasons.append("LICENCE_INCOMPAT:" + ",".join(f"{x}|{y}" for x, y in lic))
    if two_planes:
        reasons.append(
            f"DUPLICATE_CONTROL_PLANE:{a.get('control_plane')}|{b.get('control_plane')}"
        )
    return {
        "legal": not bool(mech or lic or two_planes),
        "mechanism_conflicts": mech,
        "licence_conflicts": lic,
        "duplicate_control_plane": two_planes,
        "reasons": reasons,
    }


def select_operator(a: dict, b: dict) -> str:
    """Written policy over overlap. Inputs are recorded so it can be refit."""
    overlap = jaccard(a, b)
    if overlap < 0.35:
        return "union"
    if overlap > 0.65:
        return "best-of-breed"
    return "stage-splice"


def _qualify_stage(src: dict, stage: dict) -> dict:
    out = copy.deepcopy(stage)
    out["id"] = f"{src['id']}::{stage['id']}"
    out["origin_id"] = src["id"]
    out["origin_stage_id"] = stage["id"]
    out["origin_attribution"] = src.get("attribution") or src["id"]
    out["origin_licence"] = src.get("licence")
    return out


def _fused_shell(a: dict, b: dict, operator: str, stages: list[dict]) -> dict:
    mechs: list[str] = []
    for s in stages:
        m = s.get("mechanism")
        if m and m not in mechs:
            mechs.append(m)
    licences = [a.get("licence"), b.get("licence")]
    governing = "GPL-3.0" if "GPL-3.0" in licences else (a.get("licence") or b.get("licence"))
    planes = {a.get("control_plane"), b.get("control_plane")}
    planes.discard(None)
    plane = "DUPLICATE" if len(planes) > 1 else (a.get("control_plane") or b.get("control_plane"))
    return {
        "id": f"fusion[{operator}]({a['id']}+{b['id']})",
        "kind": "fusion",
        "operator": operator,
        "source_ids": [a["id"], b["id"]],
        "attribution": sorted(
            {a.get("attribution") or a["id"], b.get("attribution") or b["id"]}
        ),
        "licence": governing,
        "inherited_licence_obligations": [
            {"source_id": a["id"], "licence": a.get("licence")},
            {"source_id": b["id"], "licence": b.get("licence")},
        ],
        "control_plane": plane,
        "has_rollback": True,
        "mechanisms": mechs,
        "stages": stages,
    }


def construct_union(a: dict, b: dict) -> dict:
    stages = [_qualify_stage(a, s) for s in a["stages"]] + [
        _qualify_stage(b, s) for s in b["stages"]
    ]
    return _fused_shell(a, b, "union", stages)


def construct_best_of_breed(a: dict, b: dict) -> dict:
    by_mech: dict[str, dict] = {}
    for src in (a, b):
        for stage in src["stages"]:
            cand = _qualify_stage(src, stage)
            mech = stage["mechanism"]
            cur = by_mech.get(mech)
            if cur is None:
                by_mech[mech] = cand
            elif float(cand["score"]) > float(cur["score"]):
                by_mech[mech] = cand
            elif float(cand["score"]) == float(cur["score"]) and cand["origin_id"] < cur[
                "origin_id"
            ]:
                by_mech[mech] = cand
    stages = sorted(by_mech.values(), key=lambda s: s["mechanism"])
    return _fused_shell(a, b, "best-of-breed", stages)


def construct_stage_splice(a: dict, b: dict) -> dict:
    host, donor = (a, b) if quality(a) >= quality(b) else (b, a)
    host_mechs = {s["mechanism"] for s in host["stages"]}
    stages = [_qualify_stage(host, s) for s in host["stages"]]
    for stage in donor["stages"]:
        if stage["mechanism"] not in host_mechs:
            stages.append(_qualify_stage(donor, stage))
    return _fused_shell(host, donor, "stage-splice", stages)


CONSTRUCTORS = {
    "union": construct_union,
    "best-of-breed": construct_best_of_breed,
    "stage-splice": construct_stage_splice,
}


def construct(operator: str, a: dict, b: dict) -> dict:
    if operator not in CONSTRUCTORS:
        raise ValueError(f"operator {operator} is named but not selected by this pair")
    return CONSTRUCTORS[operator](a, b)


def capability_loss(fusion: dict, sources: list[dict]) -> list[str]:
    have = set(fusion.get("mechanisms") or [])
    missing: list[str] = []
    for src in sources:
        for m in src.get("mechanisms") or []:
            if m not in have and m not in missing:
                missing.append(m)
    return missing


def decompose(fusion: dict) -> dict[str, dict]:
    buckets: dict[str, list[dict]] = {}
    meta: dict[str, dict] = {}
    for stage in fusion.get("stages") or []:
        oid = stage["origin_id"]
        buckets.setdefault(oid, []).append(
            {
                "id": stage["origin_stage_id"],
                "mechanism": stage["mechanism"],
                "score": stage["score"],
                "body": stage.get("body"),
            }
        )
        meta[oid] = {
            "licence": stage.get("origin_licence"),
            "attribution": stage.get("origin_attribution"),
        }
    restored: dict[str, dict] = {}
    for oid, stages in buckets.items():
        mechs: list[str] = []
        for s in stages:
            if s["mechanism"] not in mechs:
                mechs.append(s["mechanism"])
        restored[oid] = {
            "id": oid,
            "attribution": meta[oid].get("attribution"),
            "licence": meta[oid].get("licence"),
            "mechanisms": mechs,
            "stages": stages,
            "has_rollback": True,
        }
    return restored


def smoke_fingerprint(wf: dict) -> str:
    rows = [
        (s["id"], s["mechanism"], round(float(s["score"]), 6), s.get("body"))
        for s in wf.get("stages") or []
    ]
    rows.sort()
    return _sha(
        {
            "id": wf.get("id"),
            "mechanisms": sorted(wf.get("mechanisms") or []),
            "rows": rows,
        }
    )


def rollback_rehearsal(fusion: dict, originals: list[dict]) -> dict:
    restored = decompose(fusion)
    checks: list[dict] = []
    ok = True
    for src in originals:
        got = restored.get(src["id"])
        if got is None:
            ok = False
            checks.append(
                {
                    "source_id": src["id"],
                    "restored": False,
                    "reason": "missing-from-decomposition",
                }
            )
            continue
        want_fp = smoke_fingerprint(
            {
                "id": src["id"],
                "mechanisms": src.get("mechanisms"),
                "stages": src["stages"],
            }
        )
        got_fp = smoke_fingerprint(got)
        match = want_fp == got_fp
        ok = ok and match
        checks.append(
            {
                "source_id": src["id"],
                "restored": True,
                "smoke_match": match,
                "want_fp": want_fp,
                "got_fp": got_fp,
            }
        )
    return {"pass": ok, "restored_ids": sorted(restored), "checks": checks}


def _no_improvement(
    *,
    a: dict,
    b: dict,
    goal: dict,
    reason: str,
    fusion: dict | None,
    fusion_attempted: bool,
    extra: dict | None = None,
) -> dict:
    sa, sb = score(a, goal), score(b, goal)
    best, other = (a, b) if sa >= sb else (b, a)
    best_score = max(sa, sb)
    other_score = min(sa, sb)
    fusion_score = score(fusion, goal) if fusion is not None else None
    if fusion_score is None:
        margin = round(best_score - other_score, 6)
        margin_def = (
            "best_source_score - other_source_score "
            "(fusion not constructed; the gap is the usable advantage of keeping the best source)"
        )
    else:
        margin = round(best_score - fusion_score, 6)
        margin_def = "best_source_score - fusion_score (fusion did not clear the margin floor)"
    rec = {
        "terminal": "NO-IMPROVEMENT",
        "valid_terminal": True,
        "reason": reason,
        "best_source_id": best["id"],
        "best_source_score": round(best_score, 6),
        "other_source_id": other["id"],
        "other_source_score": round(other_score, 6),
        "fusion_attempted": fusion_attempted,
        "fusion_id": None if fusion is None else fusion.get("id"),
        "fusion_score": None if fusion_score is None else round(fusion_score, 6),
        "margin": margin,
        "margin_definition": margin_def,
        "margin_floor": MARGIN_FLOOR,
        "operator": None if fusion is None else fusion.get("operator"),
        "goal_id": goal.get("id"),
        "source_ids": [a["id"], b["id"]],
    }
    if extra:
        rec.update(extra)
    return rec


def certify(fusion: dict, sources: list[dict], goal: dict) -> dict:
    if len(sources) != 2:
        raise ValueError("certify expects a source pair")
    missing = capability_loss(fusion, sources)
    planes = {s.get("control_plane") for s in sources if s.get("control_plane")}
    scores = {s["id"]: score(s, goal) for s in sources}
    best_id = max(scores, key=lambda k: scores[k])
    best_score = scores[best_id]
    fusion_score = score(fusion, goal)
    margin = fusion_score - best_score
    rehearsal = rollback_rehearsal(fusion, sources)
    lineage_ok = set(rehearsal["restored_ids"]) == {s["id"] for s in sources}
    if missing:
        return _no_improvement(
            a=sources[0],
            b=sources[1],
            goal=goal,
            reason="CAPABILITY_LOSS:" + ",".join(missing),
            fusion=fusion,
            fusion_attempted=True,
            extra={"capability_missing": missing},
        )
    if len(planes) > 1 or fusion.get("control_plane") == "DUPLICATE":
        return _no_improvement(
            a=sources[0],
            b=sources[1],
            goal=goal,
            reason="DUPLICATE_CONTROL_PLANE",
            fusion=fusion,
            fusion_attempted=True,
        )
    if margin < MARGIN_FLOOR:
        return _no_improvement(
            a=sources[0],
            b=sources[1],
            goal=goal,
            reason="MARGIN_BELOW_FLOOR",
            fusion=fusion,
            fusion_attempted=True,
            extra={"observed_advantage": round(margin, 6)},
        )
    if not rehearsal["pass"] or not lineage_ok:
        return _no_improvement(
            a=sources[0],
            b=sources[1],
            goal=goal,
            reason="ROLLBACK_OR_LINEAGE_FAILED",
            fusion=fusion,
            fusion_attempted=True,
            extra={"rollback": rehearsal},
        )
    return {
        "terminal": "CERTIFIED-FUSION",
        "valid_terminal": True,
        "fusion": fusion,
        "best_source_id": best_id,
        "best_source_score": round(best_score, 6),
        "fusion_score": round(fusion_score, 6),
        "margin": round(margin, 6),
        "margin_floor": MARGIN_FLOOR,
        "capability_missing": [],
        "rollback": rehearsal,
        "lineage": {
            "source_ids": [s["id"] for s in sources],
            "operator": fusion["operator"],
            "decomposition_keys": ["origin_id", "origin_stage_id"],
            "inherited_licence_obligations": fusion["inherited_licence_obligations"],
            "attribution": fusion["attribution"],
        },
        "goal_id": goal.get("id"),
    }


def naive_always_fuse(a: dict, b: dict) -> dict:
    """Discriminating control: a fusion generator, not a decision procedure."""
    return construct_union(a, b)


def forge(
    a: dict,
    b: dict,
    goal: dict,
    *,
    skip_preconditions: bool = False,
) -> dict:
    pre = preconditions(a, b)
    policy_inputs = {
        "overlap_ratio": round(jaccard(a, b), 6),
        "conflict_present": bool(pre["mechanism_conflicts"] or pre["duplicate_control_plane"]),
        "licence_blocked": bool(pre["licence_conflicts"]),
        "cost_asymmetry": round(abs(quality(a) - quality(b)), 6),
    }
    if not skip_preconditions and not pre["legal"]:
        reason = pre["reasons"][0] if pre["reasons"] else "ILLEGAL_PAIR"
        return _no_improvement(
            a=a,
            b=b,
            goal=goal,
            reason=reason,
            fusion=None,
            fusion_attempted=False,
            extra={"preconditions": pre, "policy_inputs": policy_inputs, "operator": None},
        )
    operator = select_operator(a, b)
    fusion = construct(operator, a, b)
    result = certify(fusion, [a, b], goal)
    result["policy_inputs"] = policy_inputs
    result["preconditions"] = pre
    if result["terminal"] == "CERTIFIED-FUSION":
        result["operator"] = operator
    return result


def load_case(name: str) -> dict:
    path = HERE / "fixtures" / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def run_case(case: dict, **kwargs: Any) -> dict:
    cands = case["candidates"]
    if len(cands) != 2:
        raise ValueError("this reference forge takes exactly one source pair")
    return forge(cands[0], cands[1], case["goal"], **kwargs)
