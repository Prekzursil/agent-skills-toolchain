"""firecrawl front - dual mode: self-hosted (FIRECRAWL_API_URL) or cloud API.

Exposes: run("scrape", {"url": ...}), run("search", {"query": ...}),
run("crawl", {"url": ...}) and run("status", {"job": ...}).
"""
from __future__ import annotations

import json
import os

import requests

from .search_common import _clean, TIMEOUT, _base, config_note

CLOUD = "https://api.firecrawl.dev"


def _conf() -> tuple[str, str, str]:
    return _base("firecrawl", "FIRECRAWL_API_URL", "FIRECRAWL_API_KEY", CLOUD)


def _headers(api_key: str) -> dict:
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


def run(tool: str, args: dict) -> str:
    base, key, mode = _conf()
    if not key and mode == "cloud":
        return json.dumps({"error": "firecrawl unconfigured", "config": config_note("firecrawl", "FIRECRAWL_API_URL", "FIRECRAWL_API_KEY"),
                           "keyless_alternative": "ddg_search via fronts.search_common.ddg_search"})
    if tool == "scrape":
        r = requests.post(f"{base}/v1/scrape", headers=_headers(key),
                          json={"url": args["url"], "formats": args.get("formats", ["markdown"])},
                          timeout=TIMEOUT)
    elif tool == "search":
        r = requests.post(f"{base}/v1/search", headers=_headers(key),
                          json={"query": args["query"], "limit": args.get("limit", 8)},
                          timeout=TIMEOUT)
    elif tool == "crawl":
        r = requests.post(f"{base}/v1/crawl", headers=_headers(key),
                          json={"url": args["url"], "limit": args.get("limit", 20)},
                          timeout=TIMEOUT)
    elif tool == "status":
        r = requests.get(f"{base}/v1/crawl/{args['job']}", headers=_headers(key), timeout=TIMEOUT)
    else:
        return json.dumps({"error": f"unknown tool '{tool}'",
                           "tools": ["scrape", "search", "crawl", "status"]})
    return json.dumps({"mode": mode, "status_code": r.status_code, "body": _safe(r)})


def _safe(r: requests.Response):
    try:
        return r.json()
    except ValueError:
        return r.text[:4000]
