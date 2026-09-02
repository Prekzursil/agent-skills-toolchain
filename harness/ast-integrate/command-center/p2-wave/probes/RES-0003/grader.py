#!/usr/bin/env python3
"""Mechanical E1-E4 grader.

Ledger (catalog RES-0003 / 05-ECO frontier orchestration):
  E1 verbatim extract with a locator
  E2 multi-source (two or more independent rails)
  E3 single source
  E4 degraded-fetch where the fetcher INFERRED rather than extracted

Hedge words are a tell for E4, not the definition. An E1 extract padded with
hedges stays E1. A confident inference with no extract stays E4.

Threshold KAPPA_FLOOR is declared here, before any gold-set compute.
"""
from __future__ import annotations

from typing import Any

# Declared before kappa is computed. Do not fit this to a result.
KAPPA_FLOOR = 0.6
LABELS = ("E1", "E2", "E3", "E4")

# Tell only. Never sufficient, never used to demote a verbatim extract.
HEDGE_TELLS = (
    "perhaps",
    "maybe",
    "likely",
    "seems",
    "appears",
    "probably",
    "might",
    "could",
    "suggest",
    "apparently",
    "roughly",
    "i think",
    "it may",
)

INFERENCE_CUES = (
    "i infer",
    "fetcher inferred",
    "inferred rather than extracted",
    "must have been",
    "would have said",
    "would have contained",
    "reconstructed from memory",
    "page was probably",
    "body was empty so i wrote",
    "js-rendered blank, so the content is",
)


def _text(row: dict[str, Any]) -> str:
    return str(row.get("claim") or "")


def hedge_count(row: dict[str, Any]) -> int:
    low = _text(row).lower()
    return sum(1 for h in HEDGE_TELLS if h in low)


def has_verbatim(row: dict[str, Any]) -> bool:
    quote = str(row.get("quoted_extract") or "").strip()
    locator = str(row.get("quote_locator") or "").strip()
    return bool(quote) and bool(locator)


def independent_rail_count(row: dict[str, Any]) -> int:
    rails = row.get("rails") or []
    ids: set[str] = set()
    for rail in rails:
        if not isinstance(rail, dict):
            continue
        sid = str(rail.get("source_id") or "").strip()
        if sid:
            ids.add(sid)
    return len(ids)


def is_inferred(row: dict[str, Any]) -> bool:
    """E4 definition: fetcher invented content rather than extracting it."""
    if row.get("fetch_inferred") is True:
        return True
    if has_verbatim(row):
        return False
    low = _text(row).lower()
    if any(cue in low for cue in INFERENCE_CUES):
        return True
    degraded = row.get("fetch_degraded") is True
    extracted = row.get("body_extracted") is True
    if degraded and not extracted and independent_rail_count(row) == 0:
        return True
    return False


def grade(row: dict[str, Any]) -> str:
    """Return E1/E2/E3/E4. Does not read author_grade."""
    if "author_grade" in row and set(row.keys()) == {"author_grade"}:
        raise ValueError("grader must not be called on a label-only row")
    if is_inferred(row):
        return "E4"
    if has_verbatim(row):
        return "E1"
    n = independent_rail_count(row)
    if n >= 2:
        return "E2"
    if n == 1:
        return "E3"
    if row.get("body_extracted") is True:
        return "E3"
    return "E4"


def grade_features(row: dict[str, Any]) -> dict[str, Any]:
    pred = grade(row)
    return {
        "id": row.get("id"),
        "predicted": pred,
        "verbatim": has_verbatim(row),
        "rails": independent_rail_count(row),
        "inferred": is_inferred(row),
        "hedge_count": hedge_count(row),
        "fetch_degraded": bool(row.get("fetch_degraded")),
        "fetch_inferred": bool(row.get("fetch_inferred")),
        "body_extracted": bool(row.get("body_extracted")),
    }


def hedge_only_grade(row: dict[str, Any]) -> str:
    """Known-broken detector: demote on hedge words. Silent on confident E4."""
    if hedge_count(row) > 0:
        return "E4"
    return "E1"
