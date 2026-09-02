"""Executable workflow-scout runner. Walks STAGE_IDS; is not the WorkflowIR."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import gate
import licence
import recount
import surface
import verify
from constants import (
    ADEQUATE_COVERAGE,
    ADOPT_COVERAGE,
    DEFAULT_SOURCE_CLASSES,
    GOALS,
    MAX_RANKED,
    STAGE_IDS,
)


def load_goal(name: str) -> dict[str, Any]:
    return json.loads((GOALS / f"{name}.json").read_text(encoding="utf-8"))


def _goal_mechs(goal: dict[str, Any]) -> list[str]:
    stated = [str(m) for m in (goal.get("mechanisms") or []) if m]
    if stated:
        return stated
    text = str(goal.get("text") or "").lower()
    inferred: list[str] = []
    for mech, words in surface.load_synonyms().items():
        if any(str(w).lower() in text for w in words):
            inferred.append(str(mech))
    return inferred


def _constraints(goal: dict[str, Any]) -> dict[str, Any]:
    raw = goal.get("constraints") if isinstance(goal.get("constraints"), dict) else {}
    return {
        "licence_allow": list(raw.get("licence_allow") or []),
        "allow_build": bool(raw.get("allow_build")),
        "source_classes": list(raw.get("source_classes") or DEFAULT_SOURCE_CLASSES),
    }


def _disposition(coverage: float) -> str:
    if coverage >= ADOPT_COVERAGE:
        return "ADOPT"
    if coverage >= ADEQUATE_COVERAGE:
        return "ADAPT"
    return "REJECT"


def _pair_compose(
    goal_mechs: list[str], verified: list[dict[str, Any]]
) -> dict[str, Any] | None:
    need = set(goal_mechs)
    if len(need) < 2:
        return None
    partial: list[dict[str, Any]] = []
    for row in verified:
        have = set(row.get("mechanisms") or [])
        cov = recount.coverage(goal_mechs, list(have))
        if 0.0 < cov < ADOPT_COVERAGE and (have & need):
            partial.append(row)
    for i, left in enumerate(partial):
        for right in partial[i + 1 :]:
            union = set(left.get("mechanisms") or []) | set(right.get("mechanisms") or [])
            if not need <= union:
                continue
            joined = licence.join_most_restrictive(
                [str(left.get("licence_class")), str(right.get("licence_class"))]
            )
            if licence.is_unknown(joined):
                continue
            return {
                "id": f"compose:{left.get('id')}+{right.get('id')}",
                "disposition": "COMPOSE",
                "members": [left.get("id"), right.get("id")],
                "mechanisms": sorted(union),
                "coverage": 1.0,
                "jaccard": recount.jaccard(goal_mechs, sorted(union)),
                "quality": min(
                    float(left.get("quality") or 0.0), float(right.get("quality") or 0.0)
                ),
                "licence_class": joined,
                "provenance_anchor": [
                    (left.get("provenance") or {}).get("src"),
                    (right.get("provenance") or {}).get("src"),
                ],
                "source_class": "compose",
                "rationale": (
                    f"neither {left.get('id')} nor {right.get('id')} covers the "
                    "goal alone; union does. most-restrictive licence wins."
                ),
            }
    return None


def run(
    goal: dict[str, Any],
    *,
    skip_anti_rebuild_gate: bool = False,
) -> dict[str, Any]:
    executed: list[str] = []

    def mark(stage_id: str) -> None:
        if stage_id in STAGE_IDS and stage_id not in executed:
            executed.append(stage_id)

    mark("ingest-goal")
    mechs = _goal_mechs(goal)
    cons = _constraints(goal)

    mark("fan-out-source-classes")
    searched: list[dict[str, Any]] = []
    raw_hits: list[dict[str, Any]] = []
    mark("search-hits")
    for source_class in cons["source_classes"]:
        searched.append(surface.class_status(source_class))
        for rec in surface.iter_class(source_class):
            raw_hits.append(rec)

    unknown: list[dict[str, Any]] = []
    verified: list[dict[str, Any]] = []
    excluded_licence: list[str] = []

    mark("verify-provenance")
    mark("verify-licence")
    for rec in raw_hits:
        root = Path(str(rec.get("_anchor_root") or ""))
        prov = verify.verify_candidate(rec, root)
        rec = dict(rec)
        rec["provenance_check"] = prov
        cid = str(rec.get("id"))
        src = (rec.get("provenance") or {}).get("src")
        if prov.get("verdict") != "VERIFIED":
            unknown.append(
                {
                    "id": cid,
                    "reason": prov.get("reason"),
                    "src": src,
                    "exists_only_would_pass": bool(prov.get("exists_only_ok")),
                    "content_ok": bool(prov.get("content_ok")),
                    "source_class": rec.get("source_class"),
                    "licence_class": rec.get("licence_class"),
                }
            )
            continue
        if licence.is_unknown(rec.get("licence_class")):
            unknown.append(
                {
                    "id": cid,
                    "reason": "licence-unknown",
                    "src": src,
                    "exists_only_would_pass": True,
                    "content_ok": True,
                    "source_class": rec.get("source_class"),
                    "licence_class": rec.get("licence_class"),
                }
            )
            continue
        if not licence.allowed(rec.get("licence_class"), cons["licence_allow"] or None):
            excluded_licence.append(cid)
            continue
        verified.append(rec)

    mark("decompose-mechanisms")
    scored: list[dict[str, Any]] = []
    for rec in verified:
        row = recount.score_row(mechs, rec)
        row["record"] = rec
        scored.append(row)
    adequate = [s for s in scored if float(s["coverage"]) >= ADEQUATE_COVERAGE]
    adequate.sort(key=lambda s: (-float(s["coverage"]), -float(s["quality"]), str(s["id"])))

    mark("rank-dispositions")
    ranked: list[dict[str, Any]] = []
    for s in adequate[:MAX_RANKED]:
        rec = s["record"]
        ranked.append(
            {
                "id": rec.get("id"),
                "disposition": _disposition(float(s["coverage"])),
                "coverage": s["coverage"],
                "jaccard": s["jaccard"],
                "quality": s["quality"],
                "licence_class": rec.get("licence_class"),
                "provenance_anchor": (rec.get("provenance") or {}).get("src"),
                "source_class": rec.get("source_class"),
                "mechanisms": list(rec.get("mechanisms") or []),
                "rationale": (
                    f"coverage={s['coverage']:.2f} jaccard={s['jaccard']:.2f} "
                    f"licence={rec.get('licence_class')} "
                    f"src={(rec.get('provenance') or {}).get('src')}"
                ),
            }
        )

    compose = _pair_compose(mechs, verified)
    if compose is not None and not any(r.get("disposition") == "ADOPT" for r in ranked):
        ranked.append(compose)

    mark("anti-rebuild-gate")
    gate_verdict = gate.check(mechs, verified, skip=skip_anti_rebuild_gate)
    build: dict[str, Any] | None = None
    if cons["allow_build"]:
        if skip_anti_rebuild_gate:
            build = {
                "disposition": "BUILD",
                "gate": "SKIPPED",
                "rationale": "mutant path: BUILD emitted without anti-rebuild",
            }
        elif gate_verdict.get("block_build"):
            build = None
        elif not ranked:
            build = {
                "disposition": "BUILD",
                "gate": "PASS",
                "rationale": "no adequate existing candidate; anti-rebuild found no close hit",
            }

    mark("characterise-gap")
    nearest = None
    if scored:
        top = max(scored, key=lambda s: (float(s["coverage"]), float(s["quality"])))
        if float(top["coverage"]) < ADEQUATE_COVERAGE:
            nearest = {
                "id": top["id"],
                "coverage": top["coverage"],
                "licence_class": top["licence_class"],
            }
    gap = {
        "adequate": bool(ranked),
        "missing_mechanisms": list(mechs) if not ranked else [],
        "searched_source_classes": [s["source_class"] for s in searched],
        "nearest_existing_below_threshold": nearest,
        "n_raw_hits": len(raw_hits),
        "n_verified": len(verified),
        "n_unknown_needs_probe": len(unknown),
        "excluded_licence_ids": excluded_licence,
        "anti_rebuild_citation": gate_verdict.get("cited_id"),
    }

    mark("emit-result")
    return {
        "unit_id": "WFA-0127",
        "goal_id": goal.get("id"),
        "goal_mechanisms": mechs,
        "stages_executed": executed,
        "searched_source_classes": searched,
        "ranked": ranked,
        "ranked_ids": [r.get("id") for r in ranked],
        "unknown_needs_probe": unknown,
        "build_recommendation": build,
        "anti_rebuild": gate_verdict,
        "gap": gap,
        "skip_anti_rebuild_gate": bool(skip_anti_rebuild_gate),
        "empty_honest": (not ranked) and build is None,
    }
