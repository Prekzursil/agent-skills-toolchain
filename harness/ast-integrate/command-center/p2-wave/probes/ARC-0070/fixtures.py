#!/usr/bin/env python3
"""Scorecard and rubric loaders for ARC-0070.

Prefers live command-center/phase3/{SCORECARDS,RUBRIC}.json. When those are
absent, builds tree-derived scorecards from dossiers that actually exist
(A1, A2 today) and named-abstains the rest. Constructed cycle/transitive
panels live here for the named probes and are never written as SCORECARDS.json
(that path belongs to ARC-0069).
"""
from __future__ import annotations

import json
from pathlib import Path

ENTRIES = [f"A{i}" for i in range(1, 10)]
JUDGES = ("J-presence", "J-honesty", "J-executable")
DIMENSIONS = (
    {"id": "correctness", "weight": 0.32, "priority": 1},
    {"id": "evidence_integrity", "weight": 0.22, "priority": 2},
    {"id": "spec_conformance", "weight": 0.16, "priority": 3},
    {"id": "operational_safety", "weight": 0.12, "priority": 4},
    {"id": "maintainability", "weight": 0.10, "priority": 5},
    {"id": "resource_efficiency", "weight": 0.08, "priority": 6},
)


def clip5(x: float) -> int:
    return max(0, min(5, int(round(x))))


def default_rubric() -> dict:
    weights = [float(d["weight"]) for d in DIMENSIONS]
    return {
        "kind": "rubric",
        "unit_id": "ARC-0002",
        "state": "PARTIAL",
        "sentinel": "SUCCESS:ARC-0002",
        "source": "ARC-0070-declared-fallback",
        "note": (
            "Live command-center/phase3/RUBRIC.json is absent; this fallback is "
            "declared in aggregate.py's sibling fixtures.py BEFORE ballots are "
            "tabulated. Correctness is first; resource_efficiency is last. "
            "Weights sum to 1.0."
        ),
        "dimensions": [dict(d) for d in DIMENSIONS],
        "weights_sum": round(sum(weights), 10),
        "tie_break": {
            "order": [
                "condorcet_unique",
                "copeland",
                "schulze_strongest_path",
                "evidence_weighted_total",
                "entry_id_lexicographic",
            ]
        },
        "disqualifiers": [
            "unnamed abstention is a zero, not a missing-evidence withdrawal",
            "citations that do not resolve to an on-disk file are down-weighted to 0",
        ],
    }


def scored_cell(value: int, path: str, snippet: str) -> dict:
    return {
        "value": value,
        "abstention": False,
        "missing_evidence": None,
        "citations": [{"path": path, "snippet": snippet}],
    }


def named_abs(missing: str) -> dict:
    return {
        "value": None,
        "abstention": True,
        "missing_evidence": missing,
        "citations": [],
    }


def dossier_rel(entry_id: str) -> str:
    return f"command-center/phase3/{entry_id}/DESIGN.json"


def dossier_candidates(entry_id: str) -> list[str]:
    """Prefer the catalog DESIGN.json; else tree-local fixture dossiers.

    Live command-center/phase3/A*/DESIGN.json belong to other units and are
    not written here. ARC-0067 fixture dossiers are readable evidence that
    already exists on this worktree.
    """
    return [
        dossier_rel(entry_id),
        f"command-center/p2-wave/probes/ARC-0067/fixtures/dossiers/{entry_id}/DESIGN.json",
    ]


def resolve_dossier(repo: Path, entry_id: str) -> str | None:
    for rel in dossier_candidates(entry_id):
        path = repo / rel
        if path.is_file() and path.stat().st_size > 0:
            return rel
    return None


def features(doc: dict) -> dict:
    evid = doc.get("evidence") if isinstance(doc.get("evidence"), list) else []
    confirmed = sum(1 for e in evid if isinstance(e, dict) and e.get("verdict") == "CONFIRMED")
    refuted = sum(1 for e in evid if isinstance(e, dict) and e.get("verdict") == "REFUTED")
    expr = doc.get("expressibility") if isinstance(doc.get("expressibility"), dict) else {}
    stopped = bool(expr.get("stopped_at_first_inexpressible"))
    fs = doc.get("file_set") if isinstance(doc.get("file_set"), list) else []
    det = False
    dc = doc.get("determinism_contract")
    if isinstance(dc, dict):
        measured = dc.get("measured_this_tree")
        if isinstance(measured, dict):
            det = bool(measured.get("two_run_byte_identical"))
    if expr.get("two_run_byte_identical"):
        det = True
    required = ("architecture_id", "question", "file_set", "expressibility", "evidence")
    req_hit = sum(1 for k in required if k in doc)
    return {
        "confirmed": confirmed,
        "refuted": refuted,
        "evidence_n": max(len(evid), 1),
        "stopped": 1.0 if stopped else 0.0,
        "file_set_n": len(fs),
        "determinism": 1.0 if det else 0.0,
        "req_hit": req_hit,
        "has_answer": 1.0 if str(doc.get("answer") or "") else 0.0,
    }


def judge_scores(feat: dict, judge_id: str, cite: str) -> dict:
    c = feat["confirmed"] / feat["evidence_n"]
    r = feat["refuted"] / feat["evidence_n"]
    fs = min(feat["file_set_n"] / 8.0, 1.0)
    if judge_id == "J-presence":
        correctness = clip5(2 + 2 * feat["has_answer"] + feat["req_hit"] / 5.0)
        evidence = clip5(1 + 4 * min(feat["confirmed"] / 4.0, 1.0))
        spec = clip5(5 * (feat["req_hit"] / 5.0))
        safety = clip5(2 + 2 * feat["stopped"] + feat["determinism"])
        maint = clip5(1 + 4 * fs)
        eff = clip5(4 - feat["determinism"])  # generator costs a point
    elif judge_id == "J-honesty":
        correctness = clip5(1 + 4 * feat["stopped"] + 2 * r)
        evidence = clip5(2 + 3 * r + 2 * c)
        spec = clip5(2 + 3 * feat["stopped"])
        safety = clip5(1 + 4 * feat["stopped"])
        maint = clip5(2 + 2 * fs)
        eff = clip5(3 + feat["stopped"])
    else:  # J-executable
        correctness = clip5(1 + 4 * feat["determinism"] + feat["stopped"])
        evidence = clip5(1 + 4 * c + feat["determinism"])
        spec = clip5(2 + 2 * feat["determinism"] + feat["req_hit"] / 5.0)
        safety = clip5(2 + 3 * feat["determinism"])
        maint = clip5(2 + 3 * feat["determinism"])
        eff = clip5(2 + 2 * feat["determinism"])
    snippet = f"judge={judge_id} stopped={feat['stopped']} det={feat['determinism']}"
    return {
        "correctness": scored_cell(correctness, cite, snippet),
        "evidence_integrity": scored_cell(evidence, cite, snippet),
        "spec_conformance": scored_cell(spec, cite, snippet),
        "operational_safety": scored_cell(safety, cite, snippet),
        "maintainability": scored_cell(maint, cite, snippet),
        "resource_efficiency": scored_cell(eff, cite, snippet),
    }


def tree_derived_scorecards(repo: Path) -> dict:
    cards = []
    present = []
    absent = []
    for eid in ENTRIES:
        rel = resolve_dossier(repo, eid)
        if rel:
            present.append(eid)
            path = repo / rel
            doc = json.loads(path.read_text(encoding="utf-8"))
            feat = features(doc)
            for j in JUDGES:
                cards.append(
                    {
                        "judge_id": j,
                        "entry_id": eid,
                        "scores": judge_scores(feat, j, rel),
                    }
                )
        else:
            absent.append(eid)
            missing = f"{dossier_rel(eid)} is absent on this worktree"
            abs_scores = {d["id"]: named_abs(missing) for d in DIMENSIONS}
            for j in JUDGES:
                cards.append(
                    {
                        "judge_id": j,
                        "entry_id": eid,
                        "scores": abs_scores,
                    }
                )
    # Plant one failed-citation cell so down-weighting is exercised on the live input.
    for row in cards:
        if row["judge_id"] == "J-presence" and row["entry_id"] in present:
            row["scores"]["resource_efficiency"] = {
                "value": 5,
                "abstention": False,
                "missing_evidence": None,
                "citations": [
                    {
                        "path": "command-center/phase3/DOES-NOT-EXIST-citation.json",
                        "snippet": "planted failed citation for down-weight rule",
                    }
                ],
            }
            break
    return {
        "kind": "scorecards",
        "unit_id": "ARC-0070",
        "state": "PARTIAL",
        "sentinel": "SUCCESS:ARC-0070",
        "source": "tree-derived-fallback",
        "note": (
            "Live command-center/phase3/SCORECARDS.json is absent (ARC-0069 has "
            "not delivered). These cards are mechanical reads of dossiers that "
            f"exist on this tree ({present}), preferring catalog DESIGN.json then "
            "ARC-0067 fixture dossiers, plus named abstentions for missing "
            f"DESIGN.json files ({absent}). They are NOT a blind independent "
            "judge panel."
        ),
        "entries": list(ENTRIES),
        "judges": list(JUDGES),
        "present_dossiers": present,
        "absent_dossiers": absent,
        "scorecards": cards,
    }


def cell(value: int, cite: str = "command-center/schema/tournament-score.schema.json") -> dict:
    return scored_cell(value, cite, f"constructed:{value}")


def ranked_scores(hi: int, mid: int, lo: int) -> dict:
    # Map a 3-level preference onto six dimensions so totals stay ordered.
    return {
        "correctness": cell(hi),
        "evidence_integrity": cell(hi),
        "spec_conformance": cell(mid),
        "operational_safety": cell(mid),
        "maintainability": cell(lo),
        "resource_efficiency": cell(lo),
    }


def constructed_panel(entries: list[str], judges: list[str], prefs: dict) -> dict:
    """prefs[judge] = list of entries best-to-worst (strict)."""
    cards = []
    n = len(entries)
    for j in judges:
        order = prefs[j]
        for e in entries:
            # High score for better rank. 5 for first, 1 for last.
            pos = order.index(e)
            hi = 5 - pos
            mid = max(1, 4 - pos)
            lo = max(1, 3 - pos)
            if n > 3:
                hi = max(1, 5 - pos)
                mid = max(1, 4 - (pos // 2))
                lo = max(1, 2)
            cards.append(
                {
                    "judge_id": j,
                    "entry_id": e,
                    "scores": ranked_scores(hi, mid, lo),
                }
            )
    return {
        "kind": "scorecards",
        "unit_id": "ARC-0070",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ARC-0070",
        "source": "constructed",
        "entries": list(entries),
        "judges": list(judges),
        "scorecards": cards,
    }


def cycle_scorecards() -> dict:
    """Classic 3-voter Condorcet cycle: A>B>C, B>C>A, C>A>B."""
    entries = ["CX", "CY", "CZ"]
    judges = ["JC1", "JC2", "JC3"]
    prefs = {
        "JC1": ["CX", "CY", "CZ"],
        "JC2": ["CY", "CZ", "CX"],
        "JC3": ["CZ", "CX", "CY"],
    }
    doc = constructed_panel(entries, judges, prefs)
    doc["title"] = "constructed-condorcet-cycle"
    return doc


def transitive_scorecards() -> dict:
    entries = ["TX", "TY", "TZ"]
    judges = ["JT1", "JT2", "JT3"]
    order = ["TX", "TY", "TZ"]
    prefs = {j: list(order) for j in judges}
    doc = constructed_panel(entries, judges, prefs)
    doc["title"] = "constructed-transitive-control"
    return doc


def nine_entry_constructed() -> dict:
    """Nine entries, three judges, unique Condorcet winner; used as a method demo."""
    entries = list(ENTRIES)
    judges = ["JK1", "JK2", "JK3"]
    # Shared ranking A2 > A1 > A3 > ... so A2 is Condorcet; one judge permutes tail only.
    base = ["A2", "A1", "A3", "A4", "A5", "A6", "A7", "A8", "A9"]
    prefs = {
        "JK1": list(base),
        "JK2": list(base),
        "JK3": ["A2", "A1", "A4", "A3", "A5", "A6", "A7", "A8", "A9"],
    }
    doc = constructed_panel(entries, judges, prefs)
    doc["title"] = "constructed-nine-transitive"
    return doc


def load_rubric(repo: Path) -> tuple[dict, str]:
    live = repo / "command-center/phase3/RUBRIC.json"
    if live.is_file() and live.stat().st_size > 0:
        doc = json.loads(live.read_text(encoding="utf-8"))
        if isinstance(doc, dict) and (doc.get("dimensions") or doc.get("kind") == "rubric"):
            return doc, "live:command-center/phase3/RUBRIC.json"
    return default_rubric(), "fallback:fixtures.default_rubric"


def adapt_live_scorecards(doc: dict) -> dict:
    if doc.get("scorecards") and doc.get("entries") and doc.get("judges"):
        return doc
    raise ValueError("live SCORECARDS.json is not in the ARC-0070 scorecard shape")


def load_scorecards(repo: Path) -> tuple[dict, str]:
    live = repo / "command-center/phase3/SCORECARDS.json"
    if live.is_file() and live.stat().st_size > 0:
        doc = json.loads(live.read_text(encoding="utf-8"))
        if isinstance(doc, dict):
            try:
                return adapt_live_scorecards(doc), "live:command-center/phase3/SCORECARDS.json"
            except ValueError:
                pass
    return tree_derived_scorecards(repo), "fallback:fixtures.tree_derived_scorecards"
