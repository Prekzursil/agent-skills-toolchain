"""Mechanical dissent-survival checks. Presence is substring, not judgement."""
from __future__ import annotations

import hashlib
from typing import Any

from fixtures import (
    DISSENTER_ID,
    GENERIC_MENTION,
    INJECTED_POSITION,
    POSITION_TOKENS,
)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def locate_minority(synthesis_text: str, injected: str, dissenter_id: str) -> dict[str, Any]:
    verbatim_index = synthesis_text.find(injected)
    attribution_needle = f"Attributed to {dissenter_id}"
    attribution_index = synthesis_text.find(attribution_needle)
    snippet = ""
    if verbatim_index >= 0:
        start = max(0, verbatim_index - 48)
        end = min(len(synthesis_text), verbatim_index + len(injected) + 48)
        snippet = synthesis_text[start:end]
    return {
        "verbatim_index": verbatim_index,
        "attribution_index": attribution_index,
        "attribution_needle": attribution_needle,
        "found_verbatim": verbatim_index >= 0,
        "found_attribution": attribution_index >= 0,
        "snippet": snippet,
    }


def recommendation_acknowledges(recommendation: str) -> dict[str, Any]:
    missing = [tok for tok in POSITION_TOKENS if tok not in recommendation]
    generic_only = GENERIC_MENTION in recommendation and bool(missing)
    return {
        "pass": not missing and not generic_only,
        "missing_tokens": missing,
        "generic_only": generic_only,
    }


def survival_verdict(run: dict[str, Any]) -> dict[str, Any]:
    """PASS only when the injected position is verbatim, attributed, and the
    recommendation names the specific position rather than a generic nod."""
    text = str(run.get("synthesis_text") or "")
    rec = str(run.get("recommendation") or "")
    loc = locate_minority(text, INJECTED_POSITION, DISSENTER_ID)
    ack = recommendation_acknowledges(rec)
    reasons: list[str] = []
    if not loc["found_verbatim"]:
        if GENERIC_MENTION in text:
            reasons.append("dissent-paraphrased-away:generic-mention-without-position")
        elif "Minority report" in text:
            reasons.append("dissent-paraphrased-away")
        else:
            reasons.append("dissent-dropped")
    if not loc["found_attribution"]:
        reasons.append("unattributed")
    if not ack["pass"]:
        reasons.append("recommendation-did-not-acknowledge-specific-position")
    report = run.get("minority_report") or {}
    if loc["found_verbatim"] and report.get("attributed_to") != DISSENTER_ID:
        reasons.append("unattributed")
    return {
        "pass": not reasons,
        "reasons": reasons,
        "location": loc,
        "recommendation_ack": ack,
        "generic_mention_present": GENERIC_MENTION in text,
    }


def fabrication_verdict(run: dict[str, Any]) -> dict[str, Any]:
    """Without a dissenter, a minority report (or the injected token) is fabricated."""
    text = str(run.get("synthesis_text") or "")
    report = run.get("minority_report")
    fabricated = bool(report) or ("## Minority report" in text) or (INJECTED_POSITION in text)
    return {
        "pass": not fabricated,
        "fabricated": fabricated,
        "classification": "fabricated-dissent" if fabricated else None,
    }


def syntheses_differ(with_run: dict[str, Any], without_run: dict[str, Any]) -> dict[str, Any]:
    a = str(with_run.get("synthesis_text") or "")
    b = str(without_run.get("synthesis_text") or "")
    ha, hb = sha256_text(a), sha256_text(b)
    rec_differ = str(with_run.get("recommendation") or "") != str(
        without_run.get("recommendation") or ""
    )
    return {
        "runs_differ": a != b and ha != hb,
        "recommendations_differ": rec_differ,
        "with_sha256": ha,
        "without_sha256": hb,
        "method": "utf-8 sha256 of synthesis_text plus recommendation inequality",
    }
