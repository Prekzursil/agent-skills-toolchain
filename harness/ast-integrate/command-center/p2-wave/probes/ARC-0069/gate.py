"""Full-read gate: citation coverage derived from the dossier, not a hand list."""
from __future__ import annotations

from typing import Any

from fixtures import GATE


def sections_present(dossier: dict[str, Any]) -> list[str]:
    """Top-level keys are the sections. Derived from the file, not hand-listed."""
    skip = {"digest"}  # digest is the anti-pattern the gate exists to fail
    return sorted(k for k in dossier.keys() if isinstance(k, str) and k not in skip)


def cited_sections(citations: list[str], present: list[str]) -> set[str]:
    present_set = set(present)
    hit: set[str] = set()
    for raw in citations:
        if not isinstance(raw, str) or not raw:
            continue
        head = raw.split(".", 1)[0]
        if head in present_set:
            hit.add(head)
        elif raw in present_set:
            hit.add(raw)
    return hit


def coverage(dossier: dict[str, Any], citations: list[str]) -> dict[str, Any]:
    present = sections_present(dossier)
    hit = cited_sections(citations, present)
    denom = len(present) or 1
    ratio = len(hit) / denom
    return {
        "present": present,
        "cited": sorted(hit),
        "ratio": round(ratio, 4),
        "threshold": GATE["threshold"],
        "pass": ratio >= GATE["threshold"] and len(hit) >= 1,
    }


def citations_from_scorecard(card: dict[str, Any]) -> list[str]:
    out: list[str] = []
    dims = card.get("dimensions") or {}
    for row in dims.values():
        if not isinstance(row, dict):
            continue
        cit = row.get("citation")
        if isinstance(cit, str):
            out.append(cit)
        missing = row.get("missing_evidence")
        if isinstance(missing, str) and missing:
            # naming the missing section is not a full-read citation of a present section
            continue
    return out


def admit(dossier: dict[str, Any], card: dict[str, Any]) -> dict[str, Any]:
    cov = coverage(dossier, citations_from_scorecard(card))
    gate = "PASS" if cov["pass"] else "FAIL"
    return {"gate": gate, "coverage": cov}


admit = admit
citations_from_scorecard = citations_from_scorecard
