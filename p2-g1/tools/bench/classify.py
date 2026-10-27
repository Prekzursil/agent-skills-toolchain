"""Classify benchmark cases by the network calls they ACTUALLY make (TST-0303).

The class comes from observed urlopen/socket-style calls recorded by the
NetworkObserver - never from a case's declared class. A case declaring
"hermetic" whose oracle hits nvd.nist.gov IS advisory-db (mismatch flagged).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

TABLE_PATH = Path(__file__).resolve().parent / "ttl_table.json"
_FALLBACK_TABLE = {
    "host_map": {
        "nvd.nist.gov": "advisory-db",
        "api.anthropic.com": "model-endpoint",
        "marketplace.visualstudio.com": "marketplace-index",
        "open-vsx.org": "marketplace-index",
        "pypi.org": "marketplace-index",
    },
    "unmapped_live_default": "unknown-live",
}


def _table() -> dict[str, Any]:
    try:
        return json.loads(TABLE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(_FALLBACK_TABLE)


def host_of(url: str) -> str:
    rest = url.split("://", 1)[1] if "://" in url else url
    return rest.split("/", 1)[0].split(":", 1)[0]


def classify_call(call: dict[str, Any], table: dict[str, Any] | None = None) -> str:
    t = table if table is not None else _table()
    url = str(call.get("url") or "")
    if not url or call.get("hermetic") or url.startswith("file:"):
        return "hermetic"
    host = host_of(url)
    return t.get("host_map", {}).get(host, t.get("unmapped_live_default", "unknown-live"))


def classify_calls(
    calls: list[dict[str, Any]] | None = None,
    table: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    rows = []
    for call in calls or []:
        rows.append(
            {"call": call, "class": classify_call(call, table)}
        )
    return rows


def classify_case(
    declared_class: str,
    calls: list[dict[str, Any]],
    table: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Observed class from the case's calls; mismatch vs declared flagged."""
    t = table if table is not None else _table()
    rows = classify_calls(calls, t)
    observed_hosts = sorted(
        {host_of(str(c.get("url") or "")) for c in calls if not c.get("hermetic")}
    )
    observed = "hermetic"
    if rows:
        non_hermetic = [r["class"] for r in rows if r["class"] != "hermetic"]
        if non_hermetic:
            observed = non_hermetic[0]
    return {
        "declared_class": declared_class,
        "observed_class": observed,
        "observed_hosts": observed_hosts,
        "mismatch": observed != declared_class,
    }
