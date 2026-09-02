#!/usr/bin/env python3
"""Live ranking / design resolution for ARC-0073. Does not invent a winner."""
from __future__ import annotations

import json
from pathlib import Path

import parser as P

RANKING_REL = "command-center/phase3/AGGREGATE-RANKING.json"
A9_REL = "command-center/phase3/A9/DESIGN.json"
HYBRID_FIXTURE_REL = "command-center/p2-wave/probes/ARC-0073/fixtures/hybrid-singular.json"
KNOWN_A1 = "command-center/phase3/A1/DESIGN.json"
KNOWN_A2 = "command-center/phase3/A2/DESIGN.json"
SINGULAR_FIXTURE_REL = "command-center/p2-wave/probes/ARC-0073/fixtures/singular.json"


def _load(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return doc if isinstance(doc, dict) else None


def winner_from_ranking(doc: dict) -> str | None:
    for key in ("winner", "condorcet_winner", "aggregate_winner"):
        val = doc.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
        if isinstance(val, dict):
            for inner in ("architecture_id", "id", "entry"):
                if isinstance(val.get(inner), str) and val[inner].strip():
                    return val[inner].strip()
    ranking = doc.get("ranking") or doc.get("order") or doc.get("entries")
    if isinstance(ranking, list) and ranking:
        first = ranking[0]
        if isinstance(first, str) and first.strip():
            return first.strip()
        if isinstance(first, dict):
            for inner in ("architecture_id", "id", "entry"):
                if isinstance(first.get(inner), str) and first[inner].strip():
                    return first[inner].strip()
    return None


def live_designs(repo: Path) -> list[dict]:
    root = repo / "command-center" / "phase3"
    rows = []
    if not root.is_dir():
        return rows
    for path in sorted(root.glob("A*/DESIGN.json")):
        rel = path.relative_to(repo).as_posix()
        ev = P.evaluate_path(path)
        rows.append(
            {
                "architecture_id": ev.get("architecture_id") or path.parent.name,
                "path": rel,
                "present": True,
                "singular": bool(ev.get("singular")),
                "zero_rows": bool(ev.get("zero_rows")),
                "row_count": len(ev.get("rows") or []),
                "duplicate_count": len(ev.get("duplicates") or []),
                "duplicates": ev.get("duplicates") or [],
                "control_planes": ev.get("control_planes") or [],
                "rows": ev.get("rows") or [],
            }
        )
    return rows


def extraction_control_live(repo: Path) -> dict:
    a1 = repo / KNOWN_A1
    ev = P.evaluate_path(a1)
    hits = P.find_row(
        ev.get("rows") or [],
        capability_id="skill.council",
        path_contains="capabilities/skills",
    )
    a2 = P.evaluate_path(repo / KNOWN_A2)
    ssot = P.find_row(a2.get("rows") or [], path_contains="REGISTRY.json")
    fixture_ev = P.evaluate_path(repo / SINGULAR_FIXTURE_REL)
    fixture_hits = P.find_row(
        fixture_ev.get("rows") or [],
        capability_id="skill.council",
        path_contains="capabilities/skills",
    )
    return {
        "a1_present": a1.is_file(),
        "a1_known_skill_found": len(hits) >= 1,
        "a1_known_row": hits[0] if hits else None,
        "a1_singular_trusted": bool(ev.get("singular")) and len(hits) >= 1,
        "a2_present": (repo / KNOWN_A2).is_file(),
        "a2_ssot_found": len(ssot) >= 1,
        "a2_singular_trusted": bool(a2.get("singular")) and len(ssot) >= 1,
        "fixture_known_skill_found": len(fixture_hits) >= 1,
        "fixture_known_row": fixture_hits[0] if fixture_hits else None,
        "fixture_singular": bool(fixture_ev.get("singular")) and len(fixture_hits) >= 1,
        "refuse_vacuous_zero": not (bool(ev.get("singular")) and len(hits) == 0),
    }


def reviewer_subject(repo: Path) -> dict:
    """Live A1 DESIGN.json when present; otherwise the singular fixture."""
    a1 = repo / KNOWN_A1
    if a1.is_file():
        doc = json.loads(a1.read_text(encoding="utf-8"))
        ev = P.evaluate(doc)
        return {
            "path": KNOWN_A1,
            "doc": doc,
            "rows": ev.get("rows") or [],
            "source": "live-DESIGN",
        }
    fixture = repo / SINGULAR_FIXTURE_REL
    doc = json.loads(fixture.read_text(encoding="utf-8"))
    ev = P.evaluate(doc)
    return {
        "path": SINGULAR_FIXTURE_REL,
        "doc": doc,
        "rows": ev.get("rows") or [],
        "source": "fixture-singular",
    }


def report(repo: Path) -> dict:
    ranking_path = repo / RANKING_REL
    ranking_doc = _load(ranking_path)
    winner_id = winner_from_ranking(ranking_doc) if ranking_doc else None
    winner_design_rel = None
    if winner_id:
        candidate = repo / "command-center" / "phase3" / winner_id / "DESIGN.json"
        if candidate.is_file():
            winner_design_rel = candidate.relative_to(repo).as_posix()

    a9 = repo / A9_REL
    a9_present = a9.is_file()
    hybrid_rel = A9_REL if a9_present else HYBRID_FIXTURE_REL
    hybrid_ev = P.evaluate_path(repo / hybrid_rel)

    designs = live_designs(repo)
    extraction = extraction_control_live(repo)

    winner_eval = None
    if winner_design_rel:
        winner_eval = next((d for d in designs if d["path"] == winner_design_rel), None)
        if winner_eval is None:
            wev = P.evaluate_path(repo / winner_design_rel)
            winner_eval = {
                "architecture_id": wev.get("architecture_id"),
                "path": winner_design_rel,
                "singular": bool(wev.get("singular")),
                "row_count": len(wev.get("rows") or []),
                "duplicates": wev.get("duplicates") or [],
                "rows": wev.get("rows") or [],
            }

    return {
        "ranking_present": ranking_path.is_file(),
        "ranking_path": RANKING_REL,
        "winner_id": winner_id,
        "winner_design_path": winner_design_rel,
        "winner": winner_eval,
        "a9_present": a9_present,
        "hybrid_source": "live-A9" if a9_present else "fixture-not-live-A9",
        "hybrid_path": hybrid_rel,
        "hybrid": {
            "architecture_id": hybrid_ev.get("architecture_id"),
            "singular": bool(hybrid_ev.get("singular")),
            "zero_rows": bool(hybrid_ev.get("zero_rows")),
            "row_count": len(hybrid_ev.get("rows") or []),
            "duplicates": hybrid_ev.get("duplicates") or [],
            "control_planes": hybrid_ev.get("control_planes") or [],
            "rows": hybrid_ev.get("rows") or [],
        },
        "live_designs": designs,
        "extraction_control": extraction,
        "invented_winner": False,
        "invented_a9": False,
    }
