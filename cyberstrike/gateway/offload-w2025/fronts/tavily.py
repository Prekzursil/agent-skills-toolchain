"""tavily front - cloud API (TAVILY_API_KEY / TAVILY_API_KEY_2), optional
self-hosted/proxy base via TAVILY_API_URL, keyless DDG fallback.

Exposes: run("search", {"query": ...}), run("extract", {"urls": [...]}).
"""
from __future__ import annotations

import json
import os

import requests

from .search_common import _clean, TIMEOUT, config_note, ddg_search

CLOUD = "https://api.tavily.com"


def _key() -> str:
    return (_clean(os.environ.get("TAVILY_API_KEY"))
            or _clean(os.environ.get("TAVILY_API_KEY_2")))


def run(tool: str, args: dict) -> str:
    base = (_clean(os.environ.get("TAVILY_API_URL")) or CLOUD).rstrip("/")
    key = _key()
    if not key:
        if tool == "search":
            return json.dumps({"mode": "keyless-ddg-fallback", "query": args["query"],
                               "results": json.loads(ddg_search(args["query"], args.get("limit", 8)))})
        return json.dumps({"error": "tavily unconfigured", "config": config_note("tavily", "TAVILY_API_URL", "TAVILY_API_KEY")})
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    if tool == "search":
        r = requests.post(f"{base}/search", headers=headers,
                          json={"query": args["query"], "max_results": args.get("limit", 8),
                                "search_depth": args.get("depth", "basic")},
                          timeout=TIMEOUT)
    elif tool == "extract":
        r = requests.post(f"{base}/extract", headers=headers,
                          json={"urls": args["urls"]}, timeout=TIMEOUT)
    else:
        return json.dumps({"error": f"unknown tool '{tool}'", "tools": ["search", "extract"]})
    try:
        body = r.json()
    except ValueError:
        body = r.text[:4000]
    return json.dumps({"mode": "api", "status_code": r.status_code, "body": body})
