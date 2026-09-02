"""Dual-rail evidence grades (05-ECO R1/R2).

E1: structured API rail AND prose source, each with permalink, fetched_at,
    http_status 200, and sha256 of captured bytes. May be cited as measured fact.
E3: only one qualifying rail. Must not be cited as measured fact.
"""
from __future__ import annotations

from typing import Any

API_KIND = "structured_api"
PROSE_KIND = "prose_source"
MEASURED = "E1"
SINGLE = "E3"


def rail_ok(rail: Any) -> bool:
    if not isinstance(rail, dict):
        return False
    if not str(rail.get("permalink") or "").startswith("http"):
        return False
    if not str(rail.get("fetched_at") or "").strip():
        return False
    if rail.get("http_status") != 200:
        return False
    sha = str(rail.get("sha256") or "")
    return len(sha) == 64 and all(c in "0123456789abcdef" for c in sha)


def grade_claim(claim: dict[str, Any]) -> str:
    rails = [r for r in (claim.get("rails") or []) if rail_ok(r)]
    kinds = {str(r.get("kind") or "") for r in rails}
    if API_KIND in kinds and PROSE_KIND in kinds:
        return MEASURED
    return SINGLE


def cited_as_measured(claim: dict[str, Any]) -> bool:
    return bool(claim.get("cited_as_measured_fact"))
