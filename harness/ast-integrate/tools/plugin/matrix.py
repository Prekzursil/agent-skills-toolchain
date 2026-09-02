"""Per-field strict-parser matrix for plugin and marketplace manifests (IMP-0459)."""
from __future__ import annotations

from typing import Any

PLANTED = "x-planted-imp0459"

PLUGIN_ALLOWED = {"version", "description", "author", "metadata", "hooks", "name"}
PLUGIN_REJECT = {"_generated", "rules", PLANTED, "x-custom", "changelog"}
MARKET_ALLOWED = {"description", "version", "metadata", "name", "packages"}
MARKET_REJECT = {"_generated", "plugin_id", PLANTED, "x-custom"}


def _row(field: str, allowed: set[str]) -> dict[str, Any]:
    ok = field in allowed
    return {
        "field": field,
        "accepted": ok,
        "rejection_message": None if ok else f"unknown field {field} rejected by strict parser",
    }


def build_matrix() -> dict[str, Any]:
    plugin_fields = sorted(PLUGIN_ALLOWED | PLUGIN_REJECT)
    market_fields = sorted(MARKET_ALLOWED | MARKET_REJECT)
    plugin = [_row(f, PLUGIN_ALLOWED) for f in plugin_fields]
    market = [_row(f, MARKET_ALLOWED) for f in market_fields]
    return {
        "plugin": plugin,
        "marketplace": market,
        "rejected_plugin_fields": [r["field"] for r in plugin if not r["accepted"]],
        "rejected_marketplace_fields": [r["field"] for r in market if not r["accepted"]],
    }
