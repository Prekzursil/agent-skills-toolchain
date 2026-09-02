#!/usr/bin/env python3
"""Leave-one-source-out engine for SYN-0012.

For each declared source S and each settled conclusion C:
  remaining_keep = C.keep - {S}
  remaining_oppose = C.oppose - {S}
  SURVIVES if remaining_keep is nonempty
  REVERSES if remaining_keep is empty and remaining_oppose is nonempty
  VANISHES if both are empty

FATAL pairs are (C, S) cells that VANISH or REVERSE.
Robustness is survives / |inventory|. This is a census of the declared
inventory, not a fitted sample.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from universe import build_universe, label_completeness  # noqa: E402

SURVIVES = "SURVIVES"
VANISHES = "VANISHES"
REVERSES = "REVERSES"

NULL_MODEL = (
    "Leave-one-source-out census of the declared source inventory. A conclusion "
    "SURVIVES a hold-out when at least one sustaining source remains; REVERSES "
    "when sustainment is empty and opposing sources remain; VANISHES when both "
    "are empty. Robustness is the fraction of inventory hold-outs in which the "
    "settled verdict SURVIVES. The sampling frame is the declared inventory "
    "itself. A sweep of 3 of 40 sources would be a SAMPLE of a larger frame "
    "and must be labelled SAMPLE; this engine never silently treats a partial "
    "sweep as complete."
)


def cell_verdict(keep: list[str], oppose: list[str], held_out: str) -> str:
    rem_keep = [s for s in keep if s != held_out]
    rem_oppose = [s for s in oppose if s != held_out]
    if rem_keep:
        return SURVIVES
    if rem_oppose:
        return REVERSES
    return VANISHES


def label_for_score(score: float, keep: list[str]) -> str:
    if score >= 1.0:
        return "ROBUST"
    if len(keep) <= 1:
        return "SINGLE-SOURCE"
    return "FRAGILE"


def analyze(universe: dict | None = None) -> dict:
    uni = universe if universe is not None else build_universe()
    sources = list(uni["sources"])
    conclusions = list(uni["conclusions"])
    source_ids = [s["id"] for s in sources]
    declared = len(source_ids)
    swept = declared
    completeness = label_completeness(swept, declared)

    cells: list[dict] = []
    fatal: list[dict] = []
    scored: list[dict] = []
    for con in conclusions:
        keep = list(con.get("keep") or [])
        oppose = list(con.get("oppose") or [])
        survives = 0
        for sid in source_ids:
            verdict = cell_verdict(keep, oppose, sid)
            cell = {
                "conclusion_id": con["id"],
                "source_id": sid,
                "verdict": verdict,
            }
            cells.append(cell)
            if verdict == SURVIVES:
                survives += 1
            else:
                fatal.append(
                    {
                        "conclusion_id": con["id"],
                        "source_id": sid,
                        "verdict": verdict,
                    }
                )
        score = survives / declared if declared else 0.0
        scored.append(
            {
                "id": con["id"],
                "text": con["text"],
                "keep": keep,
                "oppose": oppose,
                "planted": con.get("planted") or "",
                "origin": con.get("origin") or "",
                "robustness_score": score,
                "robustness_fraction": {"survives": survives, "holdouts": declared},
                "label": label_for_score(score, keep),
            }
        )

    missing_cells = declared * len(conclusions) - len(cells)
    return {
        "sources": sources,
        "source_ids": source_ids,
        "conclusions": scored,
        "matrix": {
            "rows": [c["id"] for c in scored],
            "columns": source_ids,
            "cells": cells,
        },
        "fatal_pairs": fatal,
        "holdout_space": {
            "size": declared,
            "declared_size": declared,
            "swept_size": swept,
            "completeness": completeness,
            "sample": completeness == "SAMPLE",
            "sources": [
                {"id": s["id"], "kind": s["kind"], "path": s.get("path") or "", "role": s.get("role")}
                for s in sources
            ],
        },
        "input_status": uni.get("input_status") or {},
        "merge": uni.get("merge") or {},
        "null_model": NULL_MODEL,
        "matrix_cells_expected": declared * len(conclusions),
        "matrix_cells_computed": len(cells),
        "matrix_cells_missing": missing_cells,
    }


def robustness_from_matrix(matrix: dict, conclusion_id: str) -> tuple[int, int]:
    cells = [
        c
        for c in (matrix.get("cells") or [])
        if isinstance(c, dict) and c.get("conclusion_id") == conclusion_id
    ]
    holdouts = len(cells)
    survives = sum(1 for c in cells if c.get("verdict") == SURVIVES)
    return survives, holdouts


def payload(doc: dict) -> dict:
    """Domain fields live under report when the artifact is receipt_core-shaped."""
    report = doc.get("report")
    if isinstance(report, dict) and (
        "matrix" in report or "conclusions" in report or "holdout_space" in report
    ):
        return report
    return doc


def domain_errors(doc: dict) -> list[str]:
    """Catalog schema does not pin robustness_score; this unit does."""
    if not isinstance(doc, dict):
        return ["artifact is not an object"]
    p = payload(doc)
    errs: list[str] = []
    cons = p.get("conclusions")
    if not isinstance(cons, list) or not cons:
        errs.append("conclusions missing or empty")
        cons = []
    for con in cons:
        if not isinstance(con, dict):
            errs.append("conclusion is not an object")
            continue
        cid = str(con.get("id") or "?")
        if "robustness_score" not in con:
            errs.append(f"missing robustness_score {cid}")
        frac = con.get("robustness_fraction")
        if not isinstance(frac, dict):
            errs.append(f"missing robustness_fraction {cid}")
        elif "survives" not in frac or "holdouts" not in frac:
            errs.append(f"incomplete robustness_fraction {cid}")
    if not isinstance(p.get("fatal_pairs"), list):
        errs.append("fatal_pairs not enumerated")
    matrix = p.get("matrix")
    if not isinstance(matrix, dict):
        errs.append("matrix missing")
    else:
        if not isinstance(matrix.get("cells"), list):
            errs.append("matrix.cells missing")
        if not isinstance(matrix.get("columns"), list):
            errs.append("matrix.columns missing")
        if not isinstance(matrix.get("rows"), list):
            errs.append("matrix.rows missing")
    hs = p.get("holdout_space")
    if not isinstance(hs, dict):
        errs.append("holdout_space missing")
    return errs
