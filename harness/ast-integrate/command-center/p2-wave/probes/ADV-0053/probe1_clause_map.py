#!/usr/bin/env python3
"""ADV-0053 Probe 1: map each stage to the ToS clause it touches.

Quotes the clause with its retrieval date. Does not read default-enablement
from documentation — that is Probe 2.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from clauses import CLAUSES, RETRIEVED_AT  # noqa: E402
from stages import (  # noqa: E402
    BUCKET_BLOCKER,
    clauses_for,
    enumerate_stages,
    restricted_actions_for,
    search_hub_rate_policy,
)

UNIT = "ADV-0053"


def main() -> int:
    stages = enumerate_stages()
    rows = []
    missing_quote = []
    missing_date = []
    for stage in stages:
        mapping = clauses_for(stage)
        actions = restricted_actions_for(stage)
        for item in mapping:
            if not item.get("quote"):
                missing_quote.append(stage["id"])
            if item.get("retrieved_at") != RETRIEVED_AT:
                missing_date.append(stage["id"])
        rows.append(
            {
                "id": stage["id"],
                "origin": stage.get("origin"),
                "provider": stage.get("provider"),
                "intended_access": stage.get("intended_access"),
                "restricted_actions": actions,
                "clause_count": len(mapping),
                "clauses": mapping,
            }
        )

    planted = [r for r in rows if r["id"] == "planted.restricted-default-on"][0]
    clean = [r for r in rows if r["id"] == "blueprint.customer-council.compose"][0]
    planted_has_restricted = bool(planted["restricted_actions"]) and planted["clause_count"] >= 1
    clean_has_none = clean["restricted_actions"] == []
    every_stage_named = all(r["id"] for r in rows)
    quotes_ok = not missing_quote and not missing_date
    planted_scrape = any(
        c["restriction"] == "scraping" for c in planted["clauses"]
    )

    # Catalog-declared official-API stages must still carry the clauses they
    # would touch (key-share / rate) even when they do not currently perform
    # those restricted actions.
    declared = [r for r in rows if r["origin"] == "catalog-declared"]
    declared_mapped = all(
        r["clause_count"] >= 1 or r["id"] == "mcp.searxng.web-search" for r in declared
    )
    rate_policy = search_hub_rate_policy()
    rate_ok = (not rate_policy["present"]) or (
        rate_policy["does_not_cool_on_429"]
        and rate_policy["records_429_without_cooling"]
    )

    ok = (
        every_stage_named
        and quotes_ok
        and planted_has_restricted
        and planted_scrape
        and clean_has_none
        and declared_mapped
        and rate_ok
        and len(rows) >= 8
        and len(CLAUSES) >= 10
    )
    out = {
        "probe": "probe1-clause-map",
        "unit_id": UNIT,
        "n_stages": len(rows),
        "n_clauses_pinned": len(CLAUSES),
        "retrieved_at": RETRIEVED_AT,
        "planted_restricted": planted_has_restricted,
        "planted_scrape_clause": planted_scrape,
        "clean_unrestricted": clean_has_none,
        "declared_mapped": declared_mapped,
        "search_hub_rate_policy": rate_policy,
        "missing_quote": missing_quote,
        "missing_date": missing_date,
        "bucket_names": [
            "restricted-and-default-on",
            "restricted-and-opt-in-with-documented-warning",
            "unrestricted",
        ],
        "blocker_bucket_id": BUCKET_BLOCKER,
        "stages": rows,
        "pass": ok,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"stages={len(rows)} clauses={len(CLAUSES)} planted_restricted={planted_has_restricted} "
        f"clean={clean_has_none}"
    )
    if not ok:
        print(f"FAILED:{UNIT}-probe1 clause-to-stage mapping")
        return 1
    print(f"SUCCESS:{UNIT}-probe1 clause-to-stage mapping with retrieval dates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
