"""Workflow-forge: propose variants, gate schema+static+simulation, then return or refuse.

Public `forge()` is the only caller-facing entry. A workflow that only looks right
never reaches the caller: `_try_release` is the single success path and requires
all three gates, including a passing simulation receipt.
"""
from __future__ import annotations

import inspect
from typing import Any

from errors import typed_failure
from ir import OPERATOR_RANK, UNIT, fingerprint
from operators import adapt, adopt, build, compose, try_splice
from simulate import simulate
from validate import schema_validate, static_validate

HERE_REL = "command-center/p2-wave/probes/IMP-0212/forge.py"


def _gates(workflow: dict[str, Any]) -> dict[str, Any]:
    schema_ok, schema_errs = schema_validate(workflow)
    if schema_ok:
        static_ok, static_errs = static_validate(workflow)
    else:
        static_ok, static_errs = False, ["skipped: schema-invalid"]
    sim: dict[str, Any]
    if schema_ok and static_ok:
        sim = simulate(workflow)
    else:
        sim = {
            "ok": False,
            "pass": False,
            "error_code": "NOT_RUN",
            "errors": ["not-run: prior-gate-failed"],
            "zero_egress": True,
            "zero_spawn": True,
        }
    sim_ok = bool(sim.get("ok"))
    return {
        "schema": {"ok": schema_ok, "errors": schema_errs},
        "static": {"ok": static_ok, "errors": static_errs},
        "simulation": sim,
        "all_passed": bool(schema_ok and static_ok and sim_ok),
    }


def _first_fail(gates: dict[str, Any]) -> dict[str, str]:
    if not gates["schema"]["ok"]:
        return {
            "code": "SCHEMA_INVALID",
            "detail": "; ".join(gates["schema"]["errors"][:4]),
        }
    if not gates["static"]["ok"]:
        return {
            "code": "STATIC_INVALID",
            "detail": "; ".join(gates["static"]["errors"][:4]),
        }
    sim = gates["simulation"]
    code = str(sim.get("error_code") or "SIMULATION_FAILED")
    if code == "UNEMULATABLE_CAPABILITY":
        return {
            "code": code,
            "detail": str(sim.get("message") or sim.get("refused_capability") or code),
        }
    return {"code": "SIMULATION_FAILED", "detail": code}


def _try_release(variant: dict[str, Any]) -> dict[str, Any] | None:
    """Return a caller payload only when schema, static, and simulation all pass."""
    wf = variant.get("workflow")
    if not isinstance(wf, dict):
        return None
    gates = _gates(wf)
    if not gates["all_passed"]:
        return None
    sim = gates["simulation"]
    if not sim.get("ok"):
        return None
    return {
        "workflow": wf,
        "gates": gates,
        "simulation_receipt": sim,
        "operator": variant.get("operator"),
        "source_ids": list(variant.get("source_ids") or []),
        "score": float(variant.get("score") or 0),
        "fingerprint": fingerprint(wf),
    }


def _candidate_workflow(entry: Any) -> dict[str, Any] | None:
    if not isinstance(entry, dict):
        return None
    wf = entry.get("workflow")
    return wf if isinstance(wf, dict) else None


def propose_variants(
    goal: str, scout: dict[str, Any], *, allow_build: bool
) -> list[dict[str, Any]]:
    variants: list[dict[str, Any]] = []
    cands = [c for c in (scout.get("candidates") or []) if isinstance(c, dict)]
    for c in cands:
        wf = _candidate_workflow(c)
        if wf is None:
            continue
        cid = str(c.get("id") or "anonymous")
        score = float(c.get("score") or 0)
        verdict = str(c.get("verdict") or "").lower()
        try:
            if verdict == "adopt" or score >= 0.8:
                variants.append(
                    {
                        "operator": "ADOPT",
                        "workflow": adopt(wf, cid),
                        "source_ids": [cid],
                        "score": score,
                    }
                )
            variants.append(
                {
                    "operator": "ADAPT",
                    "workflow": adapt(wf, goal, cid),
                    "source_ids": [cid],
                    "score": score * 0.9,
                }
            )
        except (KeyError, TypeError, ValueError):
            variants.append(
                {
                    "operator": "ADAPT",
                    "workflow": wf,
                    "source_ids": [cid],
                    "score": score,
                }
            )
    for i, a in enumerate(cands):
        wa = _candidate_workflow(a)
        if wa is None:
            continue
        for b in cands[i + 1 :]:
            wb = _candidate_workflow(b)
            if wb is None:
                continue
            ids = [str(a.get("id")), str(b.get("id"))]
            merged, _err = try_splice(wa, wb)
            if merged is not None:
                variants.append(
                    {
                        "operator": "MERGE",
                        "workflow": merged,
                        "source_ids": ids,
                        "score": 0.7,
                    }
                )
            try:
                composed = compose(wa, wb)
            except (KeyError, IndexError, TypeError):
                composed = None
            if composed is not None:
                variants.append(
                    {
                        "operator": "COMPOSE",
                        "workflow": composed,
                        "source_ids": ids,
                        "score": 0.55,
                    }
                )
    has_adopt = any(v["operator"] == "ADOPT" for v in variants)
    if allow_build:
        variants.append(
            {
                "operator": "BUILD",
                "workflow": build(goal),
                "source_ids": [],
                "score": 0.2 if has_adopt else 0.4,
            }
        )
    return variants


def select(released: list[dict[str, Any]]) -> dict[str, Any]:
    return sorted(
        released,
        key=lambda x: (OPERATOR_RANK[str(x["operator"])], -float(x.get("score") or 0)),
    )[0]


def _anchor(fn: Any, claim: str) -> dict[str, Any]:
    line = inspect.getsourcelines(fn)[1]
    return {
        "kind": "file:line",
        "path": HERE_REL,
        "line": line,
        "claim": claim,
        "anchor": f"{HERE_REL}:{line}",
    }


def forge(
    goal: Any,
    scout: Any,
    *,
    allow_build: bool = True,
) -> dict[str, Any]:
    """Forge an executable workflow from a goal plus scout output.

    Returns either a FORGED payload (workflow + rationale + simulation receipt)
    or a TYPED_FAILURE with workflow=None. Looks-right-but-ungated artifacts
    cannot appear on the success path.
    """
    if not isinstance(goal, str) or not goal.strip():
        return typed_failure("MISSING_GOAL", "forge requires a non-empty goal string")
    if not isinstance(scout, dict):
        return typed_failure("INVALID_SCOUT", "scout output must be an object")
    if "candidates" not in scout or not isinstance(scout.get("candidates"), list):
        return typed_failure(
            "INVALID_SCOUT", "scout output must include candidates as a list"
        )

    variants = propose_variants(goal.strip(), scout, allow_build=allow_build)
    rejected: list[dict[str, Any]] = []
    released: list[dict[str, Any]] = []
    for v in variants:
        payload = _try_release(v)
        if payload is None:
            gates = _gates(v.get("workflow") if isinstance(v.get("workflow"), dict) else {})
            rejected.append(
                {
                    "operator": v.get("operator"),
                    "source_ids": v.get("source_ids"),
                    "reason": _first_fail(gates),
                    "schema_ok": gates["schema"]["ok"],
                    "static_ok": gates["static"]["ok"],
                    "simulation_ok": bool(gates["simulation"].get("ok")),
                }
            )
        else:
            released.append(payload)

    if not released:
        codes = [r["reason"]["code"] for r in rejected if isinstance(r.get("reason"), dict)]
        if codes and all(c == codes[0] for c in codes):
            code = codes[0]
        elif variants:
            code = "LOOKS_RIGHT_REFUSED"
        else:
            code = "NO_VIABLE_VARIANT"
        return typed_failure(
            code,
            "no variant passed schema+static+simulation; nothing returned to caller",
            rejected=rejected,
        )

    winner = select(released)
    # Fail closed even if a future edit bypasses _try_release's boolean.
    if not winner["gates"]["all_passed"] or not winner["simulation_receipt"].get("ok"):
        return typed_failure(
            "LOOKS_RIGHT_REFUSED",
            "internal winner lacked a passing simulation receipt",
        )

    rationale = {
        "decision": winner["operator"],
        "policy": "ADOPT > ADAPT > MERGE > COMPOSE > BUILD",
        "unit": UNIT,
        "why": (
            f"selected {winner['operator']} because it is the highest-rank operator "
            f"whose artifact passed schema, static, and hermetic simulation"
        ),
        "passing_variants": [
            {
                "operator": p["operator"],
                "score": p["score"],
                "source_ids": p["source_ids"],
                "fingerprint": p["fingerprint"],
            }
            for p in sorted(
                released, key=lambda x: OPERATOR_RANK[str(x["operator"])]
            )
        ],
        "rejected_by_gates": rejected,
        "anti_rebuild": winner["operator"] != "BUILD"
        or not any(p["operator"] == "ADOPT" for p in released),
        "anchors": [
            _anchor(select, "select ranks ADOPT ahead of BUILD (anti-rebuild)"),
            _anchor(_try_release, "only _try_release can attach a workflow for return"),
            _anchor(_gates, "schema then static then simulate; all three required"),
        ],
    }
    return {
        "ok": True,
        "status": "FORGED",
        "operator": winner["operator"],
        "workflow": winner["workflow"],
        "rationale": rationale,
        "simulation_receipt": winner["simulation_receipt"],
        "gates": {
            "schema": winner["gates"]["schema"]["ok"],
            "static": winner["gates"]["static"]["ok"],
            "simulation": True,
        },
        "fingerprint": winner["fingerprint"],
        "source_ids": winner["source_ids"],
    }
