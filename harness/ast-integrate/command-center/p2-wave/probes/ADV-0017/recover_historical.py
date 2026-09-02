#!/usr/bin/env python3
"""Record the catalog-pin 5/88 census without treating it as today's measurement."""
from __future__ import annotations

import json
from pathlib import Path

from audit_common import CATALOG_PIN_LIVE_LARGER, REPO, UID

CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"


def load_unit() -> dict:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    for u in data.get("work_units") or []:
        if isinstance(u, dict) and u.get("id") == UID:
            return u
    return {}


def historical_pin() -> dict:
    unit = load_unit()
    inputs = list(unit.get("inputs") or [])
    q = str(unit.get("question_or_target") or "")
    pin_text = " ".join(str(x) for x in inputs)
    return {
        "cited_as_live_remeasure": False,
        "status": "catalog-pin-not-remeasured",
        "catalog_inputs": inputs,
        "catalog_mentions_5_of_88": "5 of 88" in pin_text or "5 of 88" in q,
        "catalog_mentions_28_content_differing": "28 content-differing" in pin_text,
        "catalog_live_larger_names": list(CATALOG_PIN_LIVE_LARGER),
        "note": (
            "The 2026-era 5/88 / 25 repo-larger / 3 live-larger census is a "
            "catalog pin. This Linux worktree has no live ~/.claude tree and "
            "no git history, so those counts are NOT remeasured here."
        ),
    }
