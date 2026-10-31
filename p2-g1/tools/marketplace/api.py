"""Typed marketplace registry API over a registry index document (IMP-0074).

Every handler returns ``(status, schema_name, body)`` where ``schema_name``
names the $def in schema/registry-api.schema.json the body must validate
against. Errors are structured ``{"error": {"code", "message"}}`` objects,
never bare strings.
"""
from __future__ import annotations

import base64
import json
import re
from typing import Any

API_VERSION = "1.0"
DEFAULT_LIMIT = 50
MAX_LIMIT = 200
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-_.]{0,63}$")

ENDPOINTS = (
    {"path": "/", "method": "GET"},
    {"path": "/plugins", "method": "GET"},
    {"path": "/plugins/{name}", "method": "GET"},
    {"path": "/search", "method": "GET"},
)


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def _err(status: int, code: str, message: str) -> tuple[int, str, dict[str, Any]]:
    return status, "error_response", {"error": {"code": code, "message": message}}


def _encode_cursor(offset: int) -> str:
    return base64.urlsafe_b64encode(("v1:" + str(offset)).encode()).decode().rstrip("=")


def _decode_cursor(token: str) -> int:
    pad = "=" * (-len(token) % 4)
    raw = base64.urlsafe_b64decode(token + pad).decode()
    if not raw.startswith("v1:"):
        raise ValueError("bad cursor version")
    offset = int(raw[3:])
    if offset < 0:
        raise ValueError("negative cursor")
    return offset


class RegistryApi:
    """In-process registry API bound to one index document."""

    def __init__(self, index: dict[str, Any]) -> None:
        plugins = index.get("plugins") or []
        self.name = str(index.get("name") or "registry")
        self._plugins: list[dict[str, Any]] = []
        for p in plugins:
            if isinstance(p, dict) and p.get("name"):
                self._plugins.append({
                    "name": str(p["name"]),
                    "version": str(p.get("version") or "0.0.0"),
                    "description": str(p.get("description") or ""),
                    **({"keywords": [str(k) for k in p["keywords"]]}
                       if p.get("keywords") else {}),
                    **({"source": str(p["source"])} if p.get("source") else {}),
                    **({"category": str(p["category"])} if p.get("category") else {}),
                })
        self._plugins.sort(key=lambda p: p["name"])
        self._by_name = {p["name"]: p for p in self._plugins}

    # -- handlers ----------------------------------------------------------
    def index(self) -> tuple[int, str, dict[str, Any]]:
        return 200, "index_response", {
            "name": self.name,
            "api_version": API_VERSION,
            "endpoints": [dict(e) for e in ENDPOINTS],
        }

    def list_plugins(self, query: dict[str, Any] | None = None) -> tuple[int, str, dict[str, Any]]:
        query = dict(query or {})
        limit_raw = query.get("limit")
        limit = DEFAULT_LIMIT
        if limit_raw is not None:
            if not re.fullmatch(r"\d{1,4}", str(limit_raw)):
                return _err(400, "invalid_request", "limit must be a decimal integer")
            limit = int(limit_raw)
            if limit <= 0:
                return _err(400, "invalid_request", "limit must be >= 1")
            if limit > MAX_LIMIT:
                return _err(400, "invalid_request", f"limit must be <= {MAX_LIMIT}")
        offset = 0
        cursor = query.get("cursor")
        if cursor is not None:
            try:
                offset = _decode_cursor(str(cursor))
            except Exception:
                return _err(400, "invalid_request", "cursor is not a valid token")
        page = self._plugins[offset:offset + limit]
        body: dict[str, Any] = {"plugins": page, "total": len(self._plugins)}
        if offset + limit < len(self._plugins):
            body["next_cursor"] = _encode_cursor(offset + limit)
        return 200, "plugin_list_response", body

    def get_plugin(self, name: str) -> tuple[int, str, dict[str, Any]]:
        if not isinstance(name, str) or not NAME_RE.fullmatch(name):
            return _err(400, "invalid_name", "plugin name is not in the registry grammar")
        plugin = self._by_name.get(name)
        if plugin is None:
            return _err(404, "not_found", f"plugin {name} is not published")
        return 200, "plugin_response", {"plugin": plugin}

    def search(self, query: dict[str, Any] | None = None) -> tuple[int, str, dict[str, Any]]:
        query = dict(query or {})
        q = query.get("q")
        if q is None:
            return _err(400, "invalid_request", "q is required")
        if not isinstance(q, str) or not q.strip():
            return _err(400, "invalid_request", "q must be a non-empty string")
        needle = q.casefold()
        offset = 0
        cursor = query.get("cursor")
        if cursor is not None:
            try:
                offset = _decode_cursor(str(cursor))
            except Exception:
                return _err(400, "invalid_request", "cursor is not a valid token")
        hits = [
            p for p in self._plugins
            if needle in p["name"].casefold()
            or needle in p["description"].casefold()
            or any(needle in k.casefold() for k in p.get("keywords", []))
        ]
        page = hits[offset:offset + DEFAULT_LIMIT]
        body: dict[str, Any] = {"results": page, "query": q}
        if offset + DEFAULT_LIMIT < len(hits):
            body["next_cursor"] = _encode_cursor(offset + DEFAULT_LIMIT)
        return 200, "search_response", body

    # -- routing -----------------------------------------------------------
    def dispatch(self, path: str, query: dict[str, Any] | None = None) -> tuple[int, str, dict[str, Any]]:
        path = str(path or "/")
        if path in ("/", ""):
            return self.index()
        if path == "/plugins":
            return self.list_plugins(query)
        if path == "/search":
            return self.search(query)
        m = re.fullmatch(r"/plugins/([^/]+)", path)
        if m:
            return self.get_plugin(m.group(1))
        return _err(404, "unknown_endpoint", f"no route for {path}")


def canonical_body(body: dict[str, Any]) -> str:
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
