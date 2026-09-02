#!/usr/bin/env python3
"""Known-good, known-broken, and adversarial fixtures for the E1-E4 grader."""
from __future__ import annotations

from typing import Any

from gold import GOLD

# Inline copies so a probe that only imports fixtures still ships both states.
KNOWN_GOOD: dict[str, Any] = {
    "id": "FIX-GOOD-E1",
    "role": "known-good",
    "expect": "E1",
    "claim": (
        "Extracted: 'E1 verbatim / E2 multi-source / E3 single source / E4 "
        "degraded-fetch' at 05-ECO-frontier-orchestration.md:11."
    ),
    "quoted_extract": (
        "E1 verbatim / E2 multi-source / E3 single source / E4 degraded-fetch"
    ),
    "quote_locator": "05-ECO-frontier-orchestration.md:11",
    "rails": [{"kind": "prose", "source_id": "eco-orch-11"}],
    "fetch_http_status": 200,
    "fetch_sha256": "0" * 64,
    "fetch_degraded": False,
    "fetch_inferred": False,
    "body_extracted": True,
}

KNOWN_BROKEN: dict[str, Any] = {
    "id": "FIX-BROKEN-E4",
    "role": "known-broken",
    "expect": "E4",
    "claim": (
        "JS-rendered blank, so the content is a 301 to code.claude.com. "
        "Fetcher inferred rather than extracted."
    ),
    "quoted_extract": None,
    "quote_locator": None,
    "rails": [],
    "fetch_http_status": 200,
    "fetch_sha256": None,
    "fetch_degraded": True,
    "fetch_inferred": True,
    "body_extracted": False,
}

ADV_HEDGE_E1: dict[str, Any] = dict(GOLD[0])  # R01
ADV_CONFIDENT_E4: dict[str, Any] = dict(GOLD[1])  # R02


def both_states_pair() -> tuple[dict[str, Any], dict[str, Any]]:
    """Good E1 vs the same record mutated into an inferred E4."""
    good = dict(KNOWN_GOOD)
    broken = dict(good)
    broken["id"] = "FIX-MUTANT-E4"
    broken["quoted_extract"] = None
    broken["quote_locator"] = None
    broken["rails"] = []
    broken["fetch_degraded"] = True
    broken["fetch_inferred"] = True
    broken["body_extracted"] = False
    broken["claim"] = (
        "The ledger four-tier list must have been on the page; the body was empty "
        "so I wrote it."
    )
    broken["expect"] = "E4"
    return good, broken
