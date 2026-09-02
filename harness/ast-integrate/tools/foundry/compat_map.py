"""Merge/compatibility map: every component pair plus a closed FORBIDDEN vocabulary."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

FORBIDDEN_REASONS = (
    "LICENCE-INCOMPATIBLE",
    "API-BREAKING",
    "RUNTIME-ISOLATION",
    "TRUST-TIER",
)

DEFAULT_COMPONENTS = (
    {"id": "kernel", "licence": "Apache-2.0"},
    {"id": "marketplace", "licence": "MIT"},
    {"id": "plugin", "licence": "MIT"},
    {"id": "council", "licence": "Apache-2.0"},
    {"id": "foundry", "licence": "GPL-3.0"},
)


def load_components(repo: Path | None = None) -> list[dict[str, Any]]:
    root = Path(repo) if repo is not None else Path(__file__).resolve().parents[2]
    sidecar = root / "command-center" / "foundry" / "components.json"
    if sidecar.is_file():
        doc = json.loads(sidecar.read_text(encoding="utf-8"))
        rows = doc.get("components") if isinstance(doc, dict) else doc
        if isinstance(rows, list) and rows:
            return list(rows)
    return [dict(c) for c in DEFAULT_COMPONENTS]


def load_licence_matrix(repo: Path | None = None) -> dict[str, Any]:
    return {"forbidden": {"GPL-3.0|proprietary": "LICENCE-INCOMPATIBLE"}}


def _pair_id(src: str, dst: str) -> str:
    return f"{src}->{dst}"


def _cell(src: dict, dst: dict) -> dict[str, Any]:
    a, b = src["id"], dst["id"]
    la, lb = str(src.get("licence") or ""), str(dst.get("licence") or "")
    if {"GPL-3.0", "proprietary"} <= {la, lb} or (
        "GPL" in la and lb == "proprietary"
    ) or ("GPL" in lb and la == "proprietary"):
        return {
            "src": a,
            "dst": b,
            "verdict": "FORBIDDEN",
            "reason": "LICENCE-INCOMPATIBLE",
        }
    if a == "foundry" and b == "plugin":
        return {
            "src": a,
            "dst": b,
            "verdict": "FORBIDDEN",
            "reason": "TRUST-TIER",
        }
    return {"src": a, "dst": b, "verdict": "ALLOWED", "reason": None}


def build_map(repo: Path | None = None) -> dict[str, Any]:
    components = load_components(repo)
    cells = [_cell(s, d) for s in components for d in components]
    return {
        "components": components,
        "component_count": len(components),
        "component_origin": "foundry.compat_map",
        "cells": cells,
        "forbidden_reasons": list(FORBIDDEN_REASONS),
    }


def coverage_report(report: dict[str, Any] | None) -> dict[str, Any]:
    if not report:
        return {
            "coverage_ok": False,
            "cell_count": 0,
            "unique_pair_count": 0,
            "n_squared": 0,
            "missing_pairs": ["*"],
            "extra_pairs": [],
        }
    comps = [c["id"] for c in report.get("components") or []]
    n = len(comps)
    want = {_pair_id(a, b) for a in comps for b in comps}
    have = []
    for cell in report.get("cells") or []:
        have.append(_pair_id(str(cell.get("src")), str(cell.get("dst"))))
    have_set = set(have)
    missing = sorted(want - have_set)
    extra = sorted(have_set - want)
    unique = len(have_set)
    return {
        "coverage_ok": not missing and unique == n * n and len(have) == n * n,
        "cell_count": len(have),
        "unique_pair_count": unique,
        "n_squared": n * n,
        "missing_pairs": missing,
        "extra_pairs": extra,
    }


def drop_one_cell(report: dict[str, Any], src: str, dst: str) -> dict[str, Any]:
    mutant = copy.deepcopy(report)
    mutant["cells"] = [
        c
        for c in mutant.get("cells") or []
        if not (c.get("src") == src and c.get("dst") == dst)
    ]
    return mutant


def forbidden_vocab_report(report: dict[str, Any]) -> dict[str, Any]:
    allowed = set(FORBIDDEN_REASONS)
    bad = []
    forbidden_n = 0
    for cell in report.get("cells") or []:
        if cell.get("verdict") == "FORBIDDEN":
            forbidden_n += 1
            reason = cell.get("reason")
            if reason not in allowed:
                bad.append({"pair": _pair_id(cell.get("src"), cell.get("dst")), "reason": reason})
    return {
        "vocab_ok": not bad and forbidden_n >= 1,
        "illegal_reasons": bad,
        "forbidden_n": forbidden_n,
        "closed_vocab": list(FORBIDDEN_REASONS),
    }


def inject_illegal_reason(report: dict[str, Any]) -> dict[str, Any]:
    mutant = copy.deepcopy(report)
    for cell in mutant.get("cells") or []:
        if cell.get("verdict") == "FORBIDDEN":
            cell["reason"] = "INVENTED-REASON"
            break
    return mutant


def all_allowed_mutant(report: dict[str, Any]) -> dict[str, Any]:
    mutant = copy.deepcopy(report)
    for cell in mutant.get("cells") or []:
        cell["verdict"] = "ALLOWED"
        cell["reason"] = None
    return mutant


def compose_pair(src: dict[str, Any], dst: dict[str, Any]) -> dict[str, Any]:
    cell = _cell(src, dst)
    return {
        "ok": cell["verdict"] == "ALLOWED",
        "cell": cell,
        "refused": cell["verdict"] == "FORBIDDEN",
        "reason": cell.get("reason"),
    }
