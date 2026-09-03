#!/usr/bin/env python3
"""Looker MCP Server -- FastMCP integration for Looker Business Intelligence.

Supports:
- Model & explore introspection (all_models, get_explore)
- Inline query execution (run_inline_query)
- Dashboard & Look execution
- Raw Looker 4.0 API escape hatch (looker_api_raw)

Auth resolution:
- LOOKER_BASE_URL (defaults to https://looker.bolt.eu)
- LOOKER_TOKEN (direct Bearer token) OR
- LOOKER_CLIENT_ID + LOOKER_CLIENT_SECRET (OAuth2 client credentials)
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
import urllib.error
import urllib.parse
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("looker")

DEFAULT_LOOKER_URL = os.environ.get("LOOKER_BASE_URL", "https://looker.bolt.eu").rstrip("/")
_CACHED_TOKEN: Optional[str] = os.environ.get("LOOKER_TOKEN")


def _get_auth_header() -> Dict[str, str]:
    global _CACHED_TOKEN
    if _CACHED_TOKEN:
        return {"Authorization": f"Bearer {_CACHED_TOKEN}"}

    client_id = os.environ.get("LOOKER_CLIENT_ID")
    client_secret = os.environ.get("LOOKER_CLIENT_SECRET")

    if not client_id or not client_secret:
        return {}

    login_url = f"{DEFAULT_LOOKER_URL}/api/4.0/login"
    data = urllib.parse.urlencode({
        "client_id": client_id,
        "client_secret": client_secret
    }).encode("utf-8")

    req = urllib.request.Request(login_url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            _CACHED_TOKEN = body.get("access_token")
            return {"Authorization": f"Bearer {_CACHED_TOKEN}"}
    except Exception as exc:
        sys.stderr.write(f"[LookerMCP] Auth error: {exc}\n")
        return {}


def _request(path: str, method: str = "GET", body: Optional[Dict[str, Any]] = None) -> Any:
    url = f"{DEFAULT_LOOKER_URL}/api/4.0/{path.lstrip('/')}"
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    headers.update(_get_auth_header())

    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            content_type = resp.headers.get("Content-Type", "")
            if "application/json" in content_type:
                return json.loads(resp.read().decode("utf-8"))
            return resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="ignore")
        return {
            "error": f"HTTP {exc.code} {exc.reason}",
            "details": err_body,
            "url": url,
            "hint": "Set LOOKER_TOKEN or LOOKER_CLIENT_ID/LOOKER_CLIENT_SECRET in environment if authentication failed."
        }
    except Exception as exc:
        return {"error": str(exc), "url": url}


@mcp.tool()
def looker_list_models() -> Any:
    """List all available LookML models and their associated explores."""
    return _request("lookml_models")


@mcp.tool()
def looker_get_explore(model: str, explore: str) -> Any:
    """Get full metadata for an explore, including its dimensions, measures, and joined views."""
    return _request(f"lookml_models/{model}/explores/{explore}")


@mcp.tool()
def looker_run_inline_query(
    model: str,
    view: str,
    fields: List[str],
    filters: Optional[Dict[str, str]] = None,
    limit: int = 50,
    result_format: str = "json"
) -> Any:
    """Run an inline query against a Looker explore and return the result records."""
    query_body: Dict[str, Any] = {
        "model": model,
        "view": view,
        "fields": fields,
        "limit": str(limit),
    }
    if filters:
        query_body["filters"] = filters

    return _request(f"queries/run/{result_format}", method="POST", body=query_body)


@mcp.tool()
def looker_list_dashboards(search_pattern: str = "") -> Any:
    """Search or list dashboards in Looker."""
    path = "dashboards/search"
    if search_pattern:
        path += f"?title=%{urllib.parse.quote(search_pattern)}%"
    return _request(path)


@mcp.tool()
def looker_run_look(look_id: str, result_format: str = "json", limit: int = 50) -> Any:
    """Run a saved Look by ID and return results."""
    return _request(f"looks/{look_id}/run/{result_format}?limit={limit}")


@mcp.tool()
def looker_api_raw(path: str, method: str = "GET", body_json: str = "") -> Any:
    """Execute a raw request against any Looker 4.0 REST endpoint (e.g. 'users/me', 'folders')."""
    parsed_body = json.loads(body_json) if body_json.strip() else None
    return _request(path, method=method, body=parsed_body)


if __name__ == "__main__":
    mcp.run()
