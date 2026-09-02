"""Quota table: documented vendor limits vs NOT-CHECKED live remaining.

Live subscription remaining is never guessed. This unit does not query live
vendor quota APIs (retry_policy forbids a 429 burst against a live vendor).
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"

ANTHROPIC_START_RPM = 1000
ANTHROPIC_START_SPEND_USD = 500
OPENAI_TIER1_GPT4O_RPM = 500
OPENAI_TIER1_MONTHLY_USD = 100
ANTHROPIC_DOCS = "https://platform.claude.com/docs/en/api/rate-limits"
OPENAI_DOCS = "https://platform.openai.com/docs/guides/rate-limits"


def catalog_n() -> int:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    units = data.get("work_units") or []
    return len(units)


def quota_rows(fixture_rpm_measured: int) -> list[dict]:
    return [
        {
            "id": "anthropic-start-rpm-documented",
            "vendor": "anthropic",
            "kind": "requests_per_minute",
            "status": "DOCUMENTED",
            "numeric_value": ANTHROPIC_START_RPM,
            "unit": "rpm",
            "source": ANTHROPIC_DOCS,
            "note": "Start-tier Messages RPM on the public table. Not this-org remaining.",
        },
        {
            "id": "openai-tier1-gpt4o-rpm-documented",
            "vendor": "openai",
            "kind": "requests_per_minute",
            "status": "DOCUMENTED",
            "numeric_value": OPENAI_TIER1_GPT4O_RPM,
            "unit": "rpm",
            "source": OPENAI_DOCS,
            "note": "Public gpt-4o Tier-1 RPM floor. Not this-org remaining.",
        },
        {
            "id": "fixture-vendor-rpm-measured",
            "vendor": "simulated-vendor",
            "kind": "requests_per_minute",
            "status": "MEASURED",
            "numeric_value": fixture_rpm_measured,
            "unit": "rpm",
            "source": "command-center/p2-wave/probes/BLD-0058/observe.py",
            "note": "Counted as burst successes against the in-process token bucket.",
        },
        {
            "id": "anthropic-monthly-spend-remaining",
            "vendor": "anthropic",
            "kind": "subscription_remaining_usd",
            "status": "NOT-CHECKED",
            "numeric_value": None,
            "unit": "usd",
            "source": None,
            "note": "Live remaining spend is unread. Documented Start cap is $500/month but remaining is not the cap.",
            "documented_cap_usd": ANTHROPIC_START_SPEND_USD,
            "documented_cap_status": "DOCUMENTED",
        },
        {
            "id": "openai-monthly-usage-remaining",
            "vendor": "openai",
            "kind": "subscription_remaining_usd",
            "status": "NOT-CHECKED",
            "numeric_value": None,
            "unit": "usd",
            "source": None,
            "note": "Live remaining usage is unread. Documented Tier-1 monthly cap is $100 but remaining is not the cap.",
            "documented_cap_usd": OPENAI_TIER1_MONTHLY_USD,
            "documented_cap_status": "DOCUMENTED",
        },
    ]


def binding_among_checked(rows: list[dict]) -> dict:
    checked = [
        r
        for r in rows
        if r["status"] != "NOT-CHECKED"
        and isinstance(r.get("numeric_value"), (int, float))
    ]
    rpm_rows = [r for r in checked if r.get("kind") == "requests_per_minute"]
    if not rpm_rows:
        return {"id": "none", "status": "NOT-CHECKED", "reason": "no checked numeric quota"}
    winner = min(
        rpm_rows,
        key=lambda r: (
            r["numeric_value"],
            0 if r["status"] == "MEASURED" else 1,
        ),
    )
    return {
        "id": winner["id"],
        "status": winner["status"],
        "numeric_value": winner["numeric_value"],
        "unit": winner["unit"],
        "reason": (
            "Among RPM rows that are DOCUMENTED or MEASURED, the smaller ceiling "
            "binds first; MEASURED wins ties. NOT-CHECKED subscription remaining "
            "is excluded so it cannot be assumed not to bind in production."
        ),
    }
