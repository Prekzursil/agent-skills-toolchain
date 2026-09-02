#!/usr/bin/env python3
"""Mechanical mechanism extraction from an architecture dossier.

A mechanism id is {architecture_id}:{section}. Statements are taken from
typed fields (precedence, expressibility, named contracts). Prose in
`answer` is not a mechanism source.
"""
from __future__ import annotations

from typing import Any


STRING_EXPR_KEYS = (
    "catalogue_claim",
    "first_non_expressible_construct",
    "structural_rule",
)


def _add(
    rows: list[dict[str, Any]],
    arch: str,
    suffix: str,
    statement: str,
    section: str,
    source_path: str,
    source_unit: str,
) -> None:
    text = " ".join(str(statement).split())
    if not arch or not suffix or len(text) < 4:
        return
    rows.append(
        {
            "id": f"{arch}:{suffix}",
            "architecture_id": arch,
            "section": section,
            "statement": text,
            "source_path": source_path,
            "source_unit": source_unit,
        }
    )


def _dict_statement(obj: dict[str, Any], preferred: tuple[str, ...]) -> str:
    for key in preferred:
        val = obj.get(key)
        if isinstance(val, str) and len(val.strip()) >= 8:
            return val.strip()
    for key in sorted(obj):
        val = obj[key]
        if isinstance(val, str) and len(val.strip()) >= 8:
            return val.strip()
    return ""


def extract_mechanisms(doc: dict[str, Any], source_path: str) -> list[dict[str, Any]]:
    """Return the mechanism set of one dossier, sorted by id."""
    if not isinstance(doc, dict):
        return []
    arch = str(doc.get("architecture_id") or "").strip()
    if not arch:
        return []
    source_unit = str(doc.get("unit_id") or "").strip()
    rows: list[dict[str, Any]] = []

    cls = doc.get("architecture_class")
    if isinstance(cls, str) and len(cls.strip()) >= 4:
        _add(rows, arch, "class", cls.strip(), "architecture_class", source_path, source_unit)

    prec = doc.get("precedence")
    if isinstance(prec, dict):
        for key in sorted(prec):
            val = prec[key]
            section = f"precedence.{key}"
            if isinstance(val, bool):
                _add(
                    rows,
                    arch,
                    section,
                    f"{key}={str(val).lower()}",
                    section,
                    source_path,
                    source_unit,
                )
            elif isinstance(val, str) and len(val.strip()) >= 8:
                _add(rows, arch, section, val.strip(), section, source_path, source_unit)

    expr = doc.get("expressibility")
    if isinstance(expr, dict):
        for key in STRING_EXPR_KEYS:
            val = expr.get(key)
            if isinstance(val, str) and len(val.strip()) >= 8:
                section = f"expressibility.{key}"
                _add(rows, arch, section, val.strip(), section, source_path, source_unit)

    det = doc.get("determinism_contract")
    if isinstance(det, dict):
        stmt = _dict_statement(det, ("statement", "rules"))
        if not stmt and isinstance(det.get("rules"), list):
            stmt = "determinism_contract.rules=" + ";".join(
                str(x) for x in det["rules"] if isinstance(x, str)
            )
        _add(
            rows,
            arch,
            "determinism_contract",
            stmt or "determinism_contract present",
            "determinism_contract",
            source_path,
            source_unit,
        )

    hand = doc.get("hand_edit_rule")
    if isinstance(hand, dict):
        stmt = _dict_statement(hand, ("detectable", "reversible", "not_drift"))
        _add(
            rows,
            arch,
            "hand_edit_rule",
            stmt or "hand_edit_rule present",
            "hand_edit_rule",
            source_path,
            source_unit,
        )

    if isinstance(doc.get("downgrade_refusal_demo"), dict):
        demo = doc["downgrade_refusal_demo"]
        marker = ""
        anth = demo.get("anthropic") if isinstance(demo.get("anthropic"), dict) else {}
        if isinstance(anth.get("marker"), str):
            marker = anth["marker"]
        _add(
            rows,
            arch,
            "downgrade_refusal",
            marker or "downgrade_refusal_demo present",
            "downgrade_refusal_demo",
            source_path,
            source_unit,
        )

    if isinstance(doc.get("capability_tiers"), dict) and doc["capability_tiers"]:
        n = len(doc["capability_tiers"])
        _add(
            rows,
            arch,
            "capability_tiers",
            f"{n} capability-tier rows",
            "capability_tiers",
            source_path,
            source_unit,
        )

    if isinstance(doc.get("tier_map"), dict) and doc["tier_map"]:
        n = len(doc["tier_map"])
        _add(
            rows,
            arch,
            "tier_map",
            f"{n} work-unit-field tier rows",
            "tier_map",
            source_path,
            source_unit,
        )

    by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        by_id[row["id"]] = row
    return [by_id[k] for k in sorted(by_id)]


def index_by_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(r["id"]): r for r in rows if r.get("id")}
