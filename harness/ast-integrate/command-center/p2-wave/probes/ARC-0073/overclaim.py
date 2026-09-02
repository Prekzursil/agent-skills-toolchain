#!/usr/bin/env python3
"""Overclaim guards: ranking/A9 presence, prose singularity, vacuous zeros."""
from __future__ import annotations

from typing import Any


def check_overclaim(doc: dict, live: dict) -> tuple[bool, str]:
    if not isinstance(doc, dict):
        return False, "doc-not-object"
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return False, f"self-declared:{doc.get('state')}"

    ranking_claimed = bool((doc.get("inputs_on_disk") or {}).get("ranking_present"))
    if ranking_claimed != bool(live.get("ranking_present")):
        return False, "ranking-presence-mismatch"
    if not live.get("ranking_present"):
        if doc.get("winner_id"):
            return False, "invented-winner-id"
        if (doc.get("aggregate_winner") or {}).get("claimed_from_ranking") is True:
            return False, "claimed-ranking-winner-while-absent"

    a9_claimed = bool((doc.get("inputs_on_disk") or {}).get("a9_present"))
    if a9_claimed != bool(live.get("a9_present")):
        return False, "a9-presence-mismatch"
    if not live.get("a9_present"):
        src = str((doc.get("hybrid_control") or {}).get("source") or "")
        if src == "live-A9":
            return False, "claimed-live-A9-while-absent"

    if doc.get("prose_accepted_as_evidence") is True:
        return False, "prose-accepted"
    if not doc.get("computed_not_prose"):
        return False, "computed-not-prose-missing"

    ext = doc.get("extraction_control") or {}
    if not ext.get("a1_known_skill_found"):
        return False, "extraction-control-missing"
    if ext.get("trusted_zero_without_known_row"):
        return False, "vacuous-zero"
    src = str(ext.get("a1_source") or "")
    live_ext = live.get("extraction_control") or {}
    if src == "live-DESIGN" and not live_ext.get("a1_present"):
        return False, "claimed-live-A1-while-absent"
    if src == "live-DESIGN" and not live_ext.get("a1_known_skill_found"):
        return False, "claimed-live-A1-row-missing"
    if src == "live-DESIGN" and not live_ext.get("a1_singular_trusted"):
        return False, "claimed-live-A1-untrusted"

    # REFUTED rows about ranking/A9 must exist when those inputs are absent.
    claims = doc.get("claims") or []
    if not live.get("ranking_present"):
        if not any(
            c.get("verdict") == "REFUTED" and "ranking" in str(c.get("claim") or "").lower()
            for c in claims
            if isinstance(c, dict)
        ):
            return False, "missing-refute-of-ranking-winner-claim"
    return True, "ok"
