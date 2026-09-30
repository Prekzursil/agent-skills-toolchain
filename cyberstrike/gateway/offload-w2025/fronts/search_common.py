"""Shared helpers for the estate search fronts (firecrawl / tavily / exa).

Dual-mode contract for every front:
- self-hosted/local: set <PROVIDER>_API_URL (e.g. FIRECRAWL_API_URL) to your
  local instance base URL; the front talks to it (no cloud egress).
- cloud API: set <PROVIDER>_API_KEY; the front talks to the hosted API.
- keyless fallback: where the provider has no self-hosted option (tavily,
  exa) an unauthenticated DuckDuckGo search keeps the front functional
  instead of dead.
"""
from __future__ import annotations

import json
import os

import requests

TIMEOUT = int(os.environ.get("SEARCH_FRONT_TIMEOUT", "60"))


def config_note(provider: str, api_url_env: str, api_key_env: str) -> str:
    url = os.environ.get(api_url_env, "").strip()
    key = os.environ.get(api_key_env, "").strip()
    if url:
        return f"mode=self-hosted base={url}"
    if key:
        return f"mode=cloud key_sha8={_sha8(key)}"
    return (f"unconfigured: set {api_url_env} for local mode or {api_key_env} "
            f"for cloud mode; keyless DuckDuckGo fallback available")


def _sha8(value: str) -> str:
    import hashlib
    return hashlib.sha256(value.encode()).hexdigest()[:8]


def _base(provider: str, api_url_env: str, api_key_env: str, cloud_default: str) -> tuple[str, str, str]:
    """Returns (base_url, api_key, mode)."""
    url = os.environ.get(api_url_env, "").strip()
    key = os.environ.get(api_key_env, "").strip()
    if url:
        return url.rstrip("/"), key, "self-hosted"
    return cloud_default, key, "cloud"


def _clean(value: str) -> str:
    """Treat unexpanded ${VAR} templates as unset (estate env drift guard)."""
    value = (value or '').strip()
    return '' if value.startswith('${') else value


def ddg_search(query: str, max_results: int = 8) -> str:
    """Keyless DuckDuckGo search fallback."""
    from ddgs import DDGS
    with DDGS() as ddgs:
        hits = list(ddgs.text(query, max_results=max_results))
    return json.dumps(hits, indent=2)
