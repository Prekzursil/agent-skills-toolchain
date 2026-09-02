#!/usr/bin/env python3
"""Blind confirmation brief builder (CNF-0005 / spec 11034).

A confirmer receives the claim statement, the raw source, and the tests.
The implementer conclusion, receipt prose, confidence band, and summary
table are mechanically excluded by copying only the allow-list keys.
"""
from __future__ import annotations

import copy
import json
from typing import Any

# Allow-list is closed. Anything else on an implementation receipt is denied.
ALLOWED_FIELDS: tuple[str, ...] = (
    "claim_id",
    "claim_statement",
    "raw_source",
    "tests",
)

DENIED_FIELDS: tuple[str, ...] = (
    "implementer_conclusion",
    "receipt_prose",
    "confidence_band",
    "summary_table",
    "verdict",
    "prior_confirmation",
    "reviewer_notes",
    "author_confidence",
    "agent_id",
    "residual",
)


def allowed_view(receipt: dict[str, Any]) -> dict[str, Any]:
    return {k: copy.deepcopy(receipt[k]) for k in ALLOWED_FIELDS if k in receipt}


def denied_view(receipt: dict[str, Any]) -> dict[str, Any]:
    return {
        k: copy.deepcopy(v)
        for k, v in receipt.items()
        if k not in ALLOWED_FIELDS
    }


def build_brief(receipt: dict[str, Any]) -> dict[str, Any]:
    """Return the confirmer brief: allow-list fields only.

    This function is the cited builder source for CNF-0005 evidence.
    """
    if not isinstance(receipt, dict):
        raise TypeError("receipt must be a dict")
    missing = [k for k in ALLOWED_FIELDS if k not in receipt]
    if missing:
        raise KeyError(f"receipt missing allow-list fields: {missing}")
    brief = allowed_view(receipt)
    extra = [k for k in brief if k not in ALLOWED_FIELDS]
    if extra:
        raise RuntimeError(f"builder leaked extra keys: {extra}")
    return brief


def serialize_brief(brief: dict[str, Any]) -> str:
    return json.dumps(brief, sort_keys=True, ensure_ascii=False, indent=2)
