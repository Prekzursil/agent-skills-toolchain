"""Discover declared MCP servers without printing secrets or spawning them."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[3]
SECRET_KEY_HINTS = ("key", "token", "secret", "password", "credential", "auth")


def _looks_secret(name: str) -> bool:
    n = name.lower()
    return any(h in n for h in SECRET_KEY_HINTS)


def _redact_env(env: Any) -> dict[str, str]:
    if not isinstance(env, dict):
        return {}
    out: dict[str, str] = {}
    for key in env:
        k = str(key)
        out[k] = "REDACTED" if _looks_secret(k) else "PRESENT"
    return out


def _load_servers(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    if not isinstance(doc, dict):
        return {}
    block = doc.get("mcpServers")
    if isinstance(block, dict):
        return block
    return {}


def candidate_paths() -> list[Path]:
    home = Path(os.environ.get("HOME") or os.environ.get("USERPROFILE") or "/")
    return [
        REPO / ".cursor" / "mcp.json",
        REPO / ".mcp.json",
        REPO / ".claude" / "mcp.json",
        home / ".cursor" / "mcp.json",
        home / ".mcp.json",
        home / ".claude.json",
    ]


def discover() -> dict:
    found: list[dict] = []
    seen: set[str] = set()
    for path in candidate_paths():
        if not path.is_file():
            continue
        servers = _load_servers(path)
        if not servers and path.name == ".claude.json":
            continue
        rel = str(path)
        for name, spec in servers.items():
            key = f"{rel}::{name}"
            if key in seen:
                continue
            seen.add(key)
            spec = spec if isinstance(spec, dict) else {}
            transport = "http" if spec.get("url") else "stdio"
            found.append(
                {
                    "name": str(name),
                    "source": rel,
                    "transport": transport,
                    "has_command": bool(spec.get("command")),
                    "has_url": bool(spec.get("url")),
                    "env_keys": _redact_env(spec.get("env")),
                    "live_spawned": False,
                    "schema_fidelity": "NOT-CHECKED",
                    "malformed_injection": "fixture-wrapped",
                    "note": (
                        "Declared in config. Live process not spawned; "
                        "malformed-result injection uses the in-process "
                        "fixture adapter under this declared name."
                    ),
                }
            )
    return {
        "method": "config-file scan (no process spawn, no secret values)",
        "candidates": [str(p) for p in candidate_paths()],
        "servers": found,
        "count": len(found),
    }
