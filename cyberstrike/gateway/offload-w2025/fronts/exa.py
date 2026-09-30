"""exa front - cloud API only (no self-hosted upstream exists).
Keys: EXA_API_KEY / EXA_API_KEY_2. Keyless: DDG fallback for plain search.

Exposes: run("search", {"query": ...}), run("contents", {"ids": [...]}),
run("findSimilar", {"url": ...}).
"""
from __future__ import annotations

import json
import os

import requests

from .search_common import _clean, TIMEOUT, config_note, ddg_search

CLOUD = "https://api.exa.ai"


def _key() -> str:
    return (_clean(os.environ.get("EXA_API_KEY"))
            or _clean(os.environ.get("EXA_API_KEY_2")))


def run(tool: str, args: dict) -> str:
    base = (_clean(os.environ.get("EXA_API_URL")) or CLOUD).rstrip("/")
    key = _key()
    if not key:
        if tool == "search":
            return json.dumps({"mode": "keyless-ddg-fallback", "query": args["query"],
                               "results": json.loads(ddg_search(args["query"], args.get("limit", 8)))})
        return json.dumps({"error": "exa unconfigured", "config": config_note("exa", "EXA_API_URL", "EXA_API_KEY"),
                           "note": "exa has no self-hosted upstream; API key required for contents/findSimilar"})
    headers = {"x-api-key": key, "Content-Type": "application/json"}
    if tool == "search":
        payload = {"query": args["query"], "numResults": args.get("limit", 8)}
        if args.get("domain"):
            payload["includeDomains"] = [args["domain"]]
        r = requests.post(f"{base}/search", headers=headers, json=payload, timeout=TIMEOUT)
    elif tool == "contents":
        r = requests.post(f"{base}/contents", headers=headers, json={"ids": args["ids"]}, timeout=TIMEOUT)
    elif tool == "findSimilar":
        r = requests.post(f"{base}/findSimilar", headers=headers,
                          json={"url": args["url"], "numResults": args.get("limit", 8)}, timeout=TIMEOUT)
    else:
        return json.dumps({"error": f"unknown tool '{tool}'", "tools": ["search", "contents", "findSimilar"]})
    try:
        body = r.json()
    except ValueError:
        body = r.text[:4000]
    return json.dumps({"mode": "api", "status_code": r.status_code, "body": body})
