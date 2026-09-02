"""Executable workflow-forge: extract, propose, simulate, select, rationalise.

Deterministic. No network. BUILD is always proposed so a build-bias can be
measured rather than assumed away. A cosmetic BUILD whose stages use an
unknown op fails static validation and cannot be returned to the caller.
"""
from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

from fixtures import (
    CANDIDATES,
    COMPOSE_COMPATIBLE,
    CORPUS,
    LOOKS_RIGHT_OP,
    OPS,
    ADOPTION_GOAL,
    UNCOVERED_GOAL,
)

# Kind cost is the build-bias control. BUILD is always feasible for a
# well-typed goal (the interpreter implements the required ops), so without
# this cost a from-scratch workflow ties or beats a pure adoption. Probe 1
# mutants KIND_COST["BUILD"] to 0 and requires the detector to fire.
KIND_COST = {
    "ADOPT": 0.00,
    "ADAPT": 0.04,
    "MERGE": 0.08,
    "COMPOSE": 0.10,
    "BUILD": 0.25,
}
STAGE_COST = 0.01
# Smaller than KIND_COST["BUILD"]: exact-fit from-scratch is a real (weak)
# advantage that the build penalty must dominate. Zeroing the penalty lets
# this bonus elect BUILD — that is the two-sided control.
BUILD_FIT_BONUS = 0.10
INELIGIBLE_SCORE = -1.0
FORGE_INPUT_INVALID = "FORGE_INPUT_INVALID"


def _ops_of(stages: list[dict[str, Any]]) -> list[str]:
    return [str(s.get("op") or "") for s in stages]


def overlap(candidate: dict[str, Any], goal: dict[str, Any]) -> int:
    have = set(_ops_of(candidate.get("stages") or []))
    need = set(goal.get("required_ops") or [])
    return len(have & need)


def license_ok(candidate: dict[str, Any], goal: dict[str, Any]) -> bool:
    allowed = set((goal.get("constraints") or {}).get("license") or [])
    return str(candidate.get("license") or "") in allowed


def extract_mechanisms(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for cand in candidates:
        for mech in cand.get("mechanisms") or []:
            key = (str(mech.get("id")), str(cand.get("id")))
            if key in seen:
                continue
            seen.add(key)
            rec = dict(mech)
            rec["source_candidate_id"] = cand["id"]
            out.append(rec)
    return out


def static_validate(workflow: dict[str, Any]) -> tuple[bool, str]:
    stages = workflow.get("stages") or []
    if not stages:
        return False, "empty-stages"
    for stage in stages:
        op = str(stage.get("op") or "")
        if op not in OPS:
            return False, f"unknown-op:{op}"
        if not stage.get("id"):
            return False, "stage-missing-id"
    return True, "ok"


def simulate(workflow: dict[str, Any], case: dict[str, Any]) -> bool:
    ok, _reason = static_validate(workflow)
    if not ok:
        return False
    ctx: dict[str, Any] = {
        "input": copy.deepcopy(case.get("input") or {}),
        "ok": False,
    }
    for stage in workflow["stages"]:
        fn = OPS[str(stage["op"])]
        ctx = fn(ctx)
    if ctx.get("error") and not ctx.get("output"):
        ctx["ok"] = False
        ctx["output"] = {"ok": False, "error": ctx["error"]}
    bag = dict(ctx)
    bag.update(ctx.get("output") or {})
    expect = case.get("expect") or {}
    return all(bag.get(k) == v for k, v in expect.items())


def goal_cases(goal_id: str, corpus: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [c for c in corpus if c.get("goal_id") == goal_id]


def measure(
    workflow: dict[str, Any], goal: dict[str, Any], corpus: list[dict[str, Any]]
) -> dict[str, Any]:
    cases = goal_cases(goal["id"], corpus)
    passed = 0
    per: list[dict[str, Any]] = []
    for case in cases:
        hit = simulate(workflow, case)
        if hit:
            passed += 1
        per.append({"case_id": case["id"], "passed": hit})
    n = len(cases) or 1
    return {
        "cases_run": len(cases),
        "cases_passed": passed,
        "pass_rate": passed / n,
        "per_case": per,
    }


def score_of(
    kind: str,
    pass_rate: float,
    n_stages: int,
    costs: dict[str, float] | None = None,
) -> float:
    table = costs if costs is not None else KIND_COST
    bonus = BUILD_FIT_BONUS if kind == "BUILD" else 0.0
    return pass_rate - STAGE_COST * n_stages - table[kind] + bonus


def _workflow(
    *,
    wid: str,
    kind: str,
    stages: list[dict[str, Any]],
    sources: list[str],
) -> dict[str, Any]:
    return {
        "id": wid,
        "kind": kind,
        "stages": copy.deepcopy(stages),
        "source_candidate_ids": list(sources),
        "executable": True,
    }


def _adopt(candidate: dict[str, Any], goal: dict[str, Any]) -> dict[str, Any]:
    vid = f"ADOPT:{candidate['id']}"
    wf = _workflow(
        wid=f"forged.{vid}",
        kind="ADOPT",
        stages=candidate["stages"],
        sources=[candidate["id"]],
    )
    eligible = license_ok(candidate, goal)
    return {
        "variant_id": vid,
        "kind": "ADOPT",
        "source_candidate_ids": [candidate["id"]],
        "workflow": wf,
        "eligible": eligible,
        "ineligible_reason": None if eligible else "license-incompatible",
    }


def _adapt(candidate: dict[str, Any], goal: dict[str, Any]) -> dict[str, Any]:
    have = _ops_of(candidate["stages"])
    missing = [op for op in goal["required_ops"] if op not in have]
    stages = copy.deepcopy(candidate["stages"])
    for i, op in enumerate(missing, 1):
        stages.append(
            {
                "id": f"adapt-{i}",
                "op": op,
                "mechanism_id": f"mech.adapt.{op}",
            }
        )
    # Complete candidate still pays an ADAPT wrapper so it cannot tie ADOPT.
    if not missing:
        stages.append(
            {
                "id": "adapt-wrapper",
                "op": have[-1] if have else goal["required_ops"][-1],
                "mechanism_id": "mech.adapt.wrapper",
            }
        )
    vid = f"ADAPT:{candidate['id']}"
    wf = _workflow(
        wid=f"forged.{vid}",
        kind="ADAPT",
        stages=stages,
        sources=[candidate["id"]],
    )
    eligible = license_ok(candidate, goal)
    return {
        "variant_id": vid,
        "kind": "ADAPT",
        "source_candidate_ids": [candidate["id"]],
        "workflow": wf,
        "eligible": eligible,
        "ineligible_reason": None if eligible else "license-incompatible",
        "patches": missing,
    }


def _merge(a: dict[str, Any], b: dict[str, Any], goal: dict[str, Any]) -> dict[str, Any]:
    stages: list[dict[str, Any]] = []
    seen: set[str] = set()
    for src in (a, b):
        for stage in src["stages"]:
            op = str(stage["op"])
            if op in seen:
                continue
            seen.add(op)
            rec = copy.deepcopy(stage)
            rec["id"] = f"m-{src['id']}-{stage['id']}"
            stages.append(rec)
    vid = f"MERGE:{a['id']}+{b['id']}"
    wf = _workflow(
        wid=f"forged.{vid}",
        kind="MERGE",
        stages=stages,
        sources=[a["id"], b["id"]],
    )
    eligible = license_ok(a, goal) and license_ok(b, goal)
    return {
        "variant_id": vid,
        "kind": "MERGE",
        "source_candidate_ids": [a["id"], b["id"]],
        "workflow": wf,
        "eligible": eligible,
        "ineligible_reason": None if eligible else "license-incompatible",
    }


def _compose(a: dict[str, Any], b: dict[str, Any], goal: dict[str, Any]) -> dict[str, Any]:
    stages = []
    for src in (a, b):
        for stage in src["stages"]:
            rec = copy.deepcopy(stage)
            rec["id"] = f"c-{src['id']}-{stage['id']}"
            stages.append(rec)
    vid = f"COMPOSE:{a['id']}>{b['id']}"
    wf = _workflow(
        wid=f"forged.{vid}",
        kind="COMPOSE",
        stages=stages,
        sources=[a["id"], b["id"]],
    )
    eligible = license_ok(a, goal) and license_ok(b, goal)
    return {
        "variant_id": vid,
        "kind": "COMPOSE",
        "source_candidate_ids": [a["id"], b["id"]],
        "workflow": wf,
        "eligible": eligible,
        "ineligible_reason": None if eligible else "license-incompatible",
    }


def _build(goal: dict[str, Any]) -> dict[str, Any]:
    stages = [
        {
            "id": f"b{i}",
            "op": op,
            "mechanism_id": f"mech.built.{op}",
        }
        for i, op in enumerate(goal["required_ops"], 1)
    ]
    vid = "BUILD:from-scratch"
    wf = _workflow(
        wid="forged.BUILD:from-scratch", kind="BUILD", stages=stages, sources=[]
    )
    return {
        "variant_id": vid,
        "kind": "BUILD",
        "source_candidate_ids": [],
        "workflow": wf,
        "eligible": True,
        "ineligible_reason": None,
    }


def _looks_right_build(_goal: dict[str, Any]) -> dict[str, Any]:
    """Cosmetic BUILD: stages exist and look populated, op is unknown.

    static_validate must reject this. A forge that returns it has shipped a
    workflow that only looks right.
    """
    stages = [
        {
            "id": "cosmetic-1",
            "op": LOOKS_RIGHT_OP,
            "mechanism_id": "mech.cosmetic",
        }
    ]
    vid = "BUILD:looks-right"
    wf = _workflow(
        wid="forged.BUILD:looks-right", kind="BUILD", stages=stages, sources=[]
    )
    return {
        "variant_id": vid,
        "kind": "BUILD",
        "source_candidate_ids": [],
        "workflow": wf,
        "eligible": True,
        "ineligible_reason": None,
        "planted_cosmetic": True,
    }


def best_merge_pair(
    candidates: list[dict[str, Any]], goal: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    need = set(goal["required_ops"])
    best: tuple[int, int, dict[str, Any], dict[str, Any]] | None = None
    for i, a in enumerate(candidates):
        for b in candidates[i + 1 :]:
            if not license_ok(a, goal) or not license_ok(b, goal):
                continue
            union = set(_ops_of(a["stages"])) | set(_ops_of(b["stages"]))
            cover = len(union & need)
            extra = len(union - need)
            cand = (cover, -extra, a, b)
            if best is None or cand[:2] > best[:2]:
                best = cand
    if best is None:
        return None
    return best[2], best[3]


def propose_variants(
    goal: dict[str, Any], candidates: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    variants = [_adopt(c, goal) for c in candidates]
    licensed = [c for c in candidates if license_ok(c, goal)] or list(candidates)
    closest = max(
        licensed,
        key=lambda c: (overlap(c, goal), -int(c.get("scout_rank") or 99)),
    )
    variants.append(_adapt(closest, goal))
    pair = best_merge_pair(candidates, goal)
    if pair:
        variants.append(_merge(pair[0], pair[1], goal))
    by_id = {c["id"]: c for c in candidates}
    for a_id, b_id in COMPOSE_COMPATIBLE:
        if a_id in by_id and b_id in by_id:
            variants.append(_compose(by_id[a_id], by_id[b_id], goal))
    variants.append(_build(goal))
    variants.append(_looks_right_build(goal))
    return variants


def evaluate_variant(
    variant: dict[str, Any],
    goal: dict[str, Any],
    corpus: list[dict[str, Any]],
    costs: dict[str, float] | None = None,
) -> dict[str, Any]:
    rec = copy.deepcopy(variant)
    wf = rec["workflow"]
    static_ok, static_reason = static_validate(wf)
    rec["static_ok"] = static_ok
    rec["static_reason"] = static_reason
    if not rec["eligible"]:
        rec["measured_score"] = INELIGIBLE_SCORE
        rec["pass_rate"] = 0.0
        rec["simulation"] = {
            "cases_run": 0,
            "cases_passed": 0,
            "pass_rate": 0.0,
            "skipped": rec["ineligible_reason"],
        }
        return rec
    if not static_ok:
        rec["measured_score"] = INELIGIBLE_SCORE
        rec["pass_rate"] = 0.0
        rec["simulation"] = {
            "cases_run": 0,
            "cases_passed": 0,
            "pass_rate": 0.0,
            "skipped": static_reason,
        }
        return rec
    sim = measure(wf, goal, corpus)
    rec["simulation"] = sim
    rec["pass_rate"] = sim["pass_rate"]
    rec["measured_score"] = score_of(
        rec["kind"], sim["pass_rate"], len(wf["stages"]), costs
    )
    return rec


def select(
    evaluated: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    eligible = [
        v
        for v in evaluated
        if v.get("eligible")
        and v.get("static_ok")
        and v.get("measured_score", INELIGIBLE_SCORE) > INELIGIBLE_SCORE
    ]
    if not eligible:
        return None, evaluated
    eligible.sort(
        key=lambda v: (
            v["measured_score"],
            -KIND_COST.get(v["kind"], 0.0),
            -len(v["workflow"]["stages"]),
        ),
        reverse=True,
    )
    winner = eligible[0]
    rejected = [v for v in evaluated if v["variant_id"] != winner["variant_id"]]
    return winner, rejected


def why_rejected(winner: dict[str, Any], variant: dict[str, Any]) -> str:
    if not variant.get("eligible"):
        return f"ineligible:{variant.get('ineligible_reason')}"
    if not variant.get("static_ok"):
        return f"static-invalid:{variant.get('static_reason')}"
    w = winner["measured_score"]
    s = variant["measured_score"]
    return (
        f"lower measured_score than {winner['variant_id']} "
        f"({s:.4f} < {w:.4f})"
    )


def rationale_text(
    goal: dict[str, Any], winner: dict[str, Any], rejected: list[dict[str, Any]]
) -> str:
    lines = [
        f"GOAL {goal['id']}",
        (
            f"SELECTED {winner['variant_id']} kind={winner['kind']} "
            f"measured_score={winner['measured_score']:.4f} "
            f"pass_rate={winner['pass_rate']:.4f}"
        ),
    ]
    for v in rejected:
        why = why_rejected(winner, v)
        v["why_rejected"] = why
        lines.append(
            f"REJECTED {v['variant_id']} kind={v['kind']} "
            f"measured_score={v['measured_score']:.4f} "
            f"pass_rate={v.get('pass_rate', 0.0):.4f} "
            f"why={why}"
        )
    return "\n".join(lines) + "\n"


def scoreboard(evaluated: list[dict[str, Any]]) -> dict[str, float]:
    return {v["variant_id"]: float(v["measured_score"]) for v in evaluated}


def scoreboard_fingerprint(board: dict[str, float]) -> str:
    blob = json.dumps(board, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def forge(
    goal: dict[str, Any] | None,
    candidates: list[dict[str, Any]] | None = None,
    corpus: list[dict[str, Any]] | None = None,
    *,
    kind_cost: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Run the forge. kind_cost override exists so probe 1 can mutant BUILD."""
    if not isinstance(goal, dict) or not goal.get("id") or not goal.get("required_ops"):
        return {
            "ok": False,
            "error_type": FORGE_INPUT_INVALID,
            "error": "goal missing id or required_ops",
        }
    cands = list(candidates if candidates is not None else CANDIDATES)
    if not cands:
        return {
            "ok": False,
            "error_type": FORGE_INPUT_INVALID,
            "error": "empty scout candidate set",
        }
    cases = list(corpus if corpus is not None else CORPUS)
    costs = dict(KIND_COST)
    if kind_cost is not None:
        costs.update(kind_cost)
    mechanisms = extract_mechanisms(cands)
    proposed = propose_variants(goal, cands)
    evaluated = [evaluate_variant(v, goal, cases, costs) for v in proposed]
    winner, rejected = select(evaluated)
    if winner is None:
        return {
            "ok": False,
            "error_type": "FORGE_NO_ELIGIBLE_VARIANT",
            "error": "no statically valid licensed variant",
            "evaluated": evaluated,
        }
    text = rationale_text(goal, winner, rejected)
    board = scoreboard(evaluated)
    return {
        "ok": True,
        "goal_id": goal["id"],
        "extracted_mechanisms": mechanisms,
        "winner": winner,
        "rejected": rejected,
        "evaluated": evaluated,
        "rationale": text,
        "scoreboard": board,
        "scoreboard_sha256": scoreboard_fingerprint(board),
    }


def forge_adoption(kind_cost: dict[str, float] | None = None) -> dict[str, Any]:
    return forge(ADOPTION_GOAL, kind_cost=kind_cost)


def forge_uncovered(kind_cost: dict[str, float] | None = None) -> dict[str, Any]:
    return forge(UNCOVERED_GOAL, kind_cost=kind_cost)
