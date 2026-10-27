#!/usr/bin/env python3
"""Independent classifier for TST-0303: a mechanically different instrument.

Where bench.classify reads the ttl_table.json host map, this classifier
derives the class from the URL PATH SHAPE and TLD evidence directly, so the
two instruments must agree by convergence, not by sharing the table.
"""
from __future__ import annotations

from typing import Any

_ADVISORY_TLDS = ("gov", "org")
_ADVISORY_HINTS = ("nvd", "cve", "advisory", "osv")
_MODEL_HINTS = ("api.anthropic", "api.openai", "model", "v1/completions")
_MARKET_HINTS = ("marketplace", "vsix", "vsx", "pypi.org/pypi")


def _host(url: str) -> str:
    rest = url.split("://", 1)[1] if "://" in url else url
    return rest.split("/", 1)[0].split(":", 1)[0]


def independent_classify(declared: str, calls: list[dict[str, Any]]) -> dict:
    if not calls:
        return {"observed_class": "hermetic", "evidence": "zero network calls"}
    url = str(calls[0].get("url") or "")
    low = url.lower()
    host = _host(url)
    if any(h in low for h in _MODEL_HINTS):
        return {"observed_class": "model-endpoint", "evidence": host}
    if any(h in low for h in _MARKET_HINTS):
        if "pypi.org" in host:
            return {"observed_class": "package-registry", "evidence": host}
        return {"observed_class": "marketplace-index", "evidence": host}
    if any(h in low for h in _ADVISORY_HINTS):
        return {"observed_class": "advisory-db", "evidence": host}
    tld = host.rsplit(".", 1)[-1]
    if tld in _ADVISORY_TLDS:
        return {"observed_class": "advisory-db", "evidence": host}
    return {"observed_class": "unknown-live", "evidence": host}
