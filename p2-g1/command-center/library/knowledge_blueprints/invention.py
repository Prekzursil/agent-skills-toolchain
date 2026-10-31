"""Novelty grading against library fingerprints (IMP-0252)."""
from __future__ import annotations

from typing import Any

from fingerprint import mechanism_fingerprint  # noqa: E402


def reworded_duplicate(pack: dict[str, Any]) -> dict[str, Any]:
    wf = dict(pack.get("workflow") or {})
    return {
        "id": pack["id"] + "-reworded",
        "title": "A restated " + pack["id"],
        "workflow": wf,
    }


def novel_morphology_candidate() -> dict[str, Any]:
    return {
        "id": "fan-in-barrier-morphology",
        "title": "Fan-in barrier",
        "workflow": {
            "stages": ["wait", "join", "emit", "ack"],
            "edges": [["wait", "join"], ["join", "emit"], ["emit", "ack"], ["wait", "ack"]],
        },
    }


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def grade_candidate(cand: dict[str, Any], packs: list[dict[str, Any]]) -> dict[str, Any]:
    cfp = mechanism_fingerprint(cand["workflow"])
    best = 0.0
    nearest = None
    for p in packs:
        pfp = mechanism_fingerprint(p["workflow"])
        score = 1.0 if pfp == cfp else _jaccard(set(cand["workflow"]["stages"]), set(p["workflow"]["stages"]))
        if pfp == cfp:
            score = 1.0
        if score > best:
            best = score
            nearest = p["id"]
    novel = best < 0.5
    return {
        "verdict": "NOVEL" if novel else "NOT-NOVEL",
        "novelty_score": 0.0 if not novel else round(1.0 - best, 4),
        "max_jaccard": best,
        "nearest_id": nearest,
        "candidate_fingerprint": cfp,
        "volume_used": False,
    }


def grade_inventions(cands: list[dict[str, Any]], packs: list[dict[str, Any]]) -> dict[str, Any]:
    grades = [grade_candidate(c, packs) for c in cands]
    novels = [g for g in grades if g["verdict"] == "NOVEL"]
    return {
        "volume_count": len(cands),
        "volume_used_in_score": False,
        "max_novelty": max((g["novelty_score"] for g in grades), default=0.0),
        "novel_count": len(novels),
        "grades": grades,
    }
