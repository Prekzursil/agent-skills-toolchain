#!/usr/bin/env python3
"""RES-0072 evidence rails: replication status, E3, and promotion.

Catalog rules (RES-0072):
  * each mechanism cites DOI/arXiv, exact section or figure, effect size AND baseline
  * a headline number without its baseline is E3 and cannot promote
  * a saving claimed only by the router's own authors on their own benchmark is E3
    and may not promote the mechanism
  * independent-replication status is one of: replicated / self-reported-only / unknown
  * at least one router must be self-reported-only when that is the truth
"""
from __future__ import annotations

import copy
from typing import Any

ALLOWED_REPLICATION = frozenset({"replicated", "self-reported-only", "unknown"})
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})
SENTINEL = (
    "SUCCESS:RES-0072 in the receipt AND a per-router replication-status "
    "column with the benchmark each figure came from"
)
UNIT_ID = "RES-0072"
OUTPUT_REL = "command-center/research/RES-0072.json"


def derive_replication_status(row: dict[str, Any]) -> str:
    if row.get("independent_reproduction_of_this_figure") is True:
        return "replicated"
    has_figure = bool(str(row.get("effect_size") or "").strip())
    has_baseline = bool(str(row.get("baseline") or "").strip())
    has_locus = bool(str(row.get("figure_locus") or "").strip())
    has_id = bool(str(row.get("arxiv") or row.get("doi") or "").strip())
    if not (has_figure and has_baseline and has_locus and has_id):
        return "unknown"
    if row.get("own_authors_own_benchmark") is True:
        return "self-reported-only"
    return "unknown"


def derive_evidence_tier(row: dict[str, Any], status: str) -> str:
    has_baseline = bool(str(row.get("baseline") or "").strip())
    has_locus = bool(str(row.get("figure_locus") or "").strip())
    has_id = bool(str(row.get("arxiv") or row.get("doi") or "").strip())
    if not has_baseline or not has_locus or not has_id:
        return "E3"
    if status == "replicated":
        return "E1"
    if status == "self-reported-only":
        return "E3"
    return "E3"


def may_promote(tier: str, status: str) -> bool:
    return tier == "E1" and status == "replicated"


def grade_row(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    status = derive_replication_status(out)
    tier = derive_evidence_tier(out, status)
    out["replication_status"] = status
    out["evidence_tier"] = tier
    out["may_promote"] = may_promote(tier, status)
    return out


def column_from_routers(routers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    col = []
    for raw in routers:
        g = grade_row(raw)
        col.append(
            {
                "router_id": g["router_id"],
                "router_name": g["router_name"],
                "router_class": g["router_class"],
                "replication_status": g["replication_status"],
                "benchmark": g["benchmark"],
                "effect_size": g["effect_size"],
                "baseline": g["baseline"],
                "figure_locus": g["figure_locus"],
                "arxiv": g.get("arxiv") or "",
                "doi": g.get("doi") or "",
                "evidence_tier": g["evidence_tier"],
                "may_promote": g["may_promote"],
                "own_authors_own_benchmark": bool(g.get("own_authors_own_benchmark")),
                "independent_reproduction_of_this_figure": bool(
                    g.get("independent_reproduction_of_this_figure")
                ),
            }
        )
    return col


def validate_artifact(doc: dict[str, Any], expected_column: list[dict[str, Any]] | None = None) -> list[str]:
    errors: list[str] = []
    if not isinstance(doc, dict):
        return ["artifact-not-object"]
    if doc.get("unit_id") != UNIT_ID:
        errors.append(f"unit_id:{doc.get('unit_id')}")
    state = str(doc.get("state") or "").upper()
    if state in NOT_DELIVERING:
        errors.append(f"self-declared:{state}")
    text_blob = _blob(doc)
    if SENTINEL not in text_blob:
        errors.append("sentinel-absent")
    receipt = doc.get("receipt")
    if not isinstance(receipt, dict) or SENTINEL not in str(receipt.get("line") or ""):
        errors.append("sentinel-not-in-receipt")
    col = doc.get("replication_column") or doc.get("per_router_replication_status") or []
    if not isinstance(col, list) or len(col) < 3:
        errors.append("replication-column-too-small")
        return errors
    statuses = []
    for i, row in enumerate(col):
        if not isinstance(row, dict):
            errors.append(f"row-{i}-not-object")
            continue
        for key in (
            "router_id",
            "replication_status",
            "benchmark",
            "effect_size",
            "baseline",
            "figure_locus",
            "evidence_tier",
        ):
            if key not in row:
                errors.append(f"row-{i}-missing-{key}")
        st = str(row.get("replication_status") or "")
        statuses.append(st)
        if st not in ALLOWED_REPLICATION:
            errors.append(f"row-{i}-bad-status:{st}")
        if st != "unknown":
            if not str(row.get("benchmark") or "").strip():
                errors.append(f"row-{i}-benchmark-blank")
            if not str(row.get("figure_locus") or "").strip():
                errors.append(f"row-{i}-locus-blank")
        derived = derive_replication_status(row)
        if st != derived:
            errors.append(f"row-{i}-status-drift written={st} derived={derived}")
        derived_tier = derive_evidence_tier(row, derived)
        if str(row.get("evidence_tier") or "") != derived_tier:
            errors.append(
                f"row-{i}-tier-drift written={row.get('evidence_tier')} derived={derived_tier}"
            )
        want_promote = may_promote(derived_tier, derived)
        if bool(row.get("may_promote")) != want_promote:
            errors.append(f"row-{i}-promote-drift")
        if derived_tier == "E3" and row.get("may_promote") is True:
            errors.append(f"row-{i}-e3-promoted")
        if derived == "self-reported-only" and row.get("may_promote") is True:
            errors.append(f"row-{i}-self-reported-promoted")
        if derived != "unknown":
            if not str(row.get("arxiv") or row.get("doi") or "").strip():
                errors.append(f"row-{i}-missing-arxiv-doi")
            if not str(row.get("baseline") or "").strip():
                errors.append(f"row-{i}-missing-baseline")
    if "self-reported-only" not in statuses:
        errors.append("control-missing-self-reported-only")
    promoted = [r for r in col if isinstance(r, dict) and r.get("may_promote") is True]
    declared_promoted = doc.get("promoted_mechanisms") or []
    if promoted and not declared_promoted:
        errors.append("promoted-rows-not-listed")
    for item in declared_promoted:
        rid = item if isinstance(item, str) else (item or {}).get("router_id")
        match = next((r for r in col if r.get("router_id") == rid), None)
        if match is None or match.get("may_promote") is not True:
            errors.append(f"listed-promotion-not-allowed:{rid}")
    if expected_column is not None:
        got_ids = [r.get("router_id") for r in col]
        exp_ids = [r.get("router_id") for r in expected_column]
        if got_ids != exp_ids:
            errors.append(f"column-id-drift got={got_ids} exp={exp_ids}")
        for g, e in zip(col, expected_column):
            for key in (
                "replication_status",
                "benchmark",
                "effect_size",
                "baseline",
                "figure_locus",
                "evidence_tier",
                "may_promote",
            ):
                if g.get(key) != e.get(key):
                    errors.append(f"{g.get('router_id')}-mismatch-{key}")
    parts = doc.get("intended_partitions") or []
    if isinstance(parts, list) and len(parts) >= 2:
        sets = []
        for p in parts:
            ids = set((p or {}).get("source_ids") or [])
            sets.append(ids)
        for i in range(len(sets)):
            for j in range(i + 1, len(sets)):
                overlap = sets[i] & sets[j]
                if overlap:
                    errors.append(f"partition-overlap:{sorted(overlap)}")
    req = doc.get("reviewer_requirement") or {}
    if req.get("met") is True:
        revs = doc.get("reviewers") or []
        vendors = {str((r or {}).get("vendor") or "") for r in revs if isinstance(r, dict)}
        if len(vendors) < 2:
            errors.append("reviewer-requirement-claimed-met-without-two-vendors")
    if promoted:
        req_ok = isinstance(req, dict) and req.get("met") is True
        if not req_ok:
            errors.append("promotion-without-partitioned-two-vendor-review")
    return errors


def mutant_all_replicated(doc: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(doc)
    col = out.get("replication_column") or []
    for row in col:
        row["replication_status"] = "replicated"
        row["evidence_tier"] = "E1"
        row["may_promote"] = True
        row["independent_reproduction_of_this_figure"] = False
    out["promoted_mechanisms"] = [r.get("router_id") for r in col]
    return out


def mutant_strip_baseline(doc: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(doc)
    col = out.get("replication_column") or []
    if col:
        col[0]["baseline"] = ""
        col[0]["replication_status"] = "self-reported-only"
        col[0]["evidence_tier"] = "E2"
        col[0]["may_promote"] = True
    return out


def mutant_promote_e3(doc: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(doc)
    col = out.get("replication_column") or []
    for row in col:
        if row.get("evidence_tier") == "E3":
            row["may_promote"] = True
            out["promoted_mechanisms"] = [row.get("router_id")]
            break
    return out


def _blob(doc: dict[str, Any]) -> str:
    import json

    return json.dumps(doc, ensure_ascii=False)
