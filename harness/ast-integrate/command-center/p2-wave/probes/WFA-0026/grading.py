#!/usr/bin/env python3
"""Mechanical trust grader. Table lookup only; no per-source feel overrides."""
from __future__ import annotations

from typing import Any

ALLOWED_AUTHORITY = {"PRIMARY", "MAINTAINER", "PRACTITIONER", "RETELLER"}
ALLOWED_PROD = {"EXPLICIT", "IMPLIED", "NONE"}
ALLOWED_CORR = {"DUAL", "SINGLE"}


def forbidden_rule_keys(rule: dict) -> list[str]:
    """Keys that would turn the rule into per-source feel grading."""
    bad = []
    for k in rule.keys():
        lk = str(k).casefold()
        if lk in {"source_id", "url", "overrides", "feel", "exceptions"}:
            bad.append(str(k))
    return bad


def production_claim(text: str, rule: dict) -> str:
    folded = " ".join((text or "").split()).casefold()
    needles = (rule.get("production_needles") or {})
    for n in needles.get("EXPLICIT") or []:
        if n.casefold() in folded:
            return "EXPLICIT"
    for n in needles.get("IMPLIED") or []:
        if n.casefold() in folded:
            return "IMPLIED"
    return "NONE"


def authority_for_class(source_class: str, rule: dict) -> str:
    table = rule.get("authority_by_class") or {}
    auth = table.get(source_class)
    if auth not in ALLOWED_AUTHORITY:
        return "RETELLER"
    return auth


def apply_rule(
    *,
    injection_detected: bool,
    verbatim_quote: str | None,
    authority: str,
    production_claim_value: str,
    corroboration: str,
    in_vendor: bool,
) -> dict[str, Any]:
    """Pure function of features + the frozen rule tables (inlined as if/then)."""
    if injection_detected or not (verbatim_quote or "").strip():
        grade = "REJECT"
    elif (
        authority == "PRIMARY"
        and production_claim_value == "EXPLICIT"
        and corroboration == "DUAL"
    ):
        grade = "T0"
    elif (
        authority in {"MAINTAINER", "PRACTITIONER"}
        and production_claim_value == "EXPLICIT"
        and corroboration == "DUAL"
    ):
        grade = "T1"
    elif (
        authority in {"PRIMARY", "MAINTAINER", "PRACTITIONER"}
        and production_claim_value in {"EXPLICIT", "IMPLIED"}
        and (corroboration == "SINGLE" or production_claim_value == "IMPLIED")
    ):
        # IMPLIED is never a FINDING even if DUAL; SINGLE EXPLICIT is T2.
        if production_claim_value == "IMPLIED":
            grade = "T2"
        elif corroboration == "SINGLE":
            grade = "T2"
        else:
            grade = "T3"
    elif authority == "RETELLER" or production_claim_value == "NONE":
        grade = "T3"
    else:
        grade = "T3"

    if grade == "REJECT":
        disposition = "REJECTED"
    elif in_vendor:
        disposition = "DUPLICATE-OF"
    elif grade in {"T0", "T1"}:
        disposition = "FINDING"
    elif grade == "T2":
        disposition = "UNVERIFIED"
    else:
        disposition = "NOT-PROMOTED"

    return {
        "trust_grade": grade,
        "disposition": disposition,
        "promoted_to_finding": disposition == "FINDING",
    }


def unaffiliated(a: dict, b: dict) -> bool:
    if a.get("id") == b.get("id"):
        return False
    if (a.get("host") or "").casefold() == (b.get("host") or "").casefold():
        return False
    ga, gb = a.get("github_repo"), b.get("github_repo")
    if ga and gb and str(ga).casefold() == str(gb).casefold():
        return False
    return True
