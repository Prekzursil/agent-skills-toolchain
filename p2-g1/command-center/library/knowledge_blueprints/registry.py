"""Knowledge-blueprint library registry (IMP-0252)."""
from __future__ import annotations

from fingerprint import mechanism_fingerprint  # noqa: E402


def _packs() -> list[dict]:
    return [
        {
            "id": "documentation-verification",
            "workflow": {
                "stages": ["extract", "execute", "coverage"],
                "edges": [["extract", "execute"], ["execute", "coverage"]],
            },
        },
        {
            "id": "citation-hygiene",
            "workflow": {
                "stages": ["harvest", "bind", "rate"],
                "edges": [["harvest", "bind"], ["harvest", "rate"]],
            },
        },
        {
            "id": "budget-governor",
            "workflow": {
                "stages": ["meter", "trip", "refuse"],
                "edges": [["meter", "trip"], ["trip", "refuse"], ["refuse", "meter"]],
            },
        },
        {
            "id": "role-mandate-guard",
            "workflow": {
                "stages": ["classify", "act"],
                "edges": [["classify", "act"]],
            },
        },
    ]


def load_library() -> dict:
    packs = _packs()
    fps = {p["id"]: mechanism_fingerprint(p["workflow"]) for p in packs}
    collisions = len(fps) - len(set(fps.values()))
    return {
        "packs": packs,
        "fingerprints": fps,
        "fingerprint_collisions": collisions,
    }
