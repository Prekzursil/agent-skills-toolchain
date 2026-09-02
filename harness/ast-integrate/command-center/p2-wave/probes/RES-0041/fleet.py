#!/usr/bin/env python3
"""Load MCP schema fixtures and serialize them the way a client injects them.

Eager payload: tools/list analogue with name + description + inputSchema.
Deferred payload: Cursor GetDynamicTools catalog analogue — name + description
truncated to 200 characters, no inputSchema.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
CATALOG_DESC_LIMIT = 200


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def truncate_desc(text: str, limit: int = CATALOG_DESC_LIMIT) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 15] + "... [truncated]"


def load_server_file(path: Path) -> dict[str, Any]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or not doc.get("id") or not isinstance(doc.get("tools"), list):
        raise ValueError(f"bad server fixture {path}")
    doc["_fixture_path"] = str(path.relative_to(HERE.parent.parent.parent.parent)).replace("\\", "/")
    return doc


def load_fleet() -> list[dict[str, Any]]:
    paths = sorted(FIXTURES.glob("live/*.json")) + sorted(FIXTURES.glob("harness/*.json"))
    if len(paths) < 2:
        raise RuntimeError(f"fleet too small: {paths}")
    servers = [load_server_file(p) for p in paths]
    ids = [s["id"] for s in servers]
    if len(ids) != len(set(ids)):
        raise RuntimeError(f"duplicate server ids: {ids}")
    return servers


def eager_tool(tool: dict[str, Any]) -> dict[str, Any]:
    return {
        "description": str(tool.get("description") or ""),
        "inputSchema": tool.get("inputSchema") if isinstance(tool.get("inputSchema"), dict) else {},
        "name": str(tool.get("name") or ""),
    }


def deferred_tool(tool: dict[str, Any]) -> dict[str, Any]:
    return {
        "description": truncate_desc(str(tool.get("description") or "")),
        "name": str(tool.get("name") or ""),
    }


def eager_blob(server: dict[str, Any]) -> str:
    return canonical(
        {
            "server": server["id"],
            "tools": [eager_tool(t) for t in server["tools"]],
        }
    )


def deferred_blob(server: dict[str, Any]) -> str:
    return canonical(
        {
            "server": server["id"],
            "tools": [deferred_tool(t) for t in server["tools"]],
        }
    )


def home_mcp_inventory() -> dict[str, Any]:
    home = Path.home()
    candidates = [
        home / ".mcp.json",
        home / ".cursor" / "mcp.json",
        HERE.parents[3] / ".cursor" / "mcp.json",
        HERE.parents[3] / "mcp.json",
    ]
    rows = []
    for p in candidates:
        rows.append(
            {
                "path": str(p),
                "exists": p.is_file(),
                "bytes": p.stat().st_size if p.is_file() else 0,
            }
        )
    return {
        "any_present": any(r["exists"] for r in rows),
        "candidates": rows,
    }
