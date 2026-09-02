"""Installed-component inventory fixtures for IMP-0476.

Seven health checks:
  ledger, deploy  — two independent probes, both OK (positive controls)
  hooks, mcp      — a single declared probe that is OK (must render NOT-CHECKED)
  skills          — two probes, same method (not independent) both OK
  router          — two independent probes that disagree
  cache           — two independent probes that both fail
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
COMPONENTS = HERE / "fixtures" / "components"
INVENTORY_PATH = HERE / "fixtures" / "inventory.json"

LEDGER = b'{"component":"ledger","healthy":true}\n'
HOOKS = b'{"component":"hooks","healthy":true}\n'
SKILLS = b'{"component":"skills","healthy":true}\n'
MCP = b'{"component":"mcp","healthy":true}\n'
ROUTER = b'{"component":"router","healthy":false}\n'
DEPLOY = b'{"component":"deploy","healthy":true}\n'
WRONG_HASH = "0" * 64


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def ensure_fixtures() -> dict[str, Any]:
    _write(COMPONENTS / "ledger" / "marker.json", LEDGER)
    _write(COMPONENTS / "hooks" / "marker.json", HOOKS)
    _write(COMPONENTS / "skills" / "marker.json", SKILLS)
    _write(COMPONENTS / "mcp" / "marker.json", MCP)
    _write(COMPONENTS / "router" / "marker.json", ROUTER)
    _write(COMPONENTS / "deploy" / "marker.json", DEPLOY)
    cache_dir = COMPONENTS / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    missing = cache_dir / "marker.json"
    if missing.exists():
        missing.unlink()

    inventory = {
        "id": "installed-component-inventory",
        "unit_id": "IMP-0476",
        "checks": [
            {
                "id": "ledger.writable",
                "component": "ledger",
                "title": "Ledger is present and byte-authentic (positive control)",
                "probes": [
                    {
                        "id": "ledger-stat",
                        "method": "file-stat",
                        "path": "ledger/marker.json",
                        "min_bytes": 8,
                        "command": "file-stat:ledger/marker.json",
                    },
                    {
                        "id": "ledger-hash",
                        "method": "content-hash",
                        "path": "ledger/marker.json",
                        "sha256": sha256_bytes(LEDGER),
                        "command": "content-hash:ledger/marker.json",
                    },
                ],
            },
            {
                "id": "hooks.loaded",
                "component": "hooks",
                "title": "Hooks marker (single declared probe — must NOT-CHECKED)",
                "probes": [
                    {
                        "id": "hooks-stat",
                        "method": "file-stat",
                        "path": "hooks/marker.json",
                        "min_bytes": 8,
                        "command": "file-stat:hooks/marker.json",
                    }
                ],
            },
            {
                "id": "skills.registered",
                "component": "skills",
                "title": "Skills markers (cloned file-stat — not independent)",
                "probes": [
                    {
                        "id": "skills-stat-a",
                        "method": "file-stat",
                        "path": "skills/marker.json",
                        "min_bytes": 8,
                        "command": "file-stat:skills/marker.json#a",
                    },
                    {
                        "id": "skills-stat-b",
                        "method": "file-stat",
                        "path": "skills/marker.json",
                        "min_bytes": 8,
                        "command": "file-stat:skills/marker.json#b",
                    },
                ],
            },
            {
                "id": "mcp.reachable",
                "component": "mcp",
                "title": "MCP marker (one probe declared, second source undeclared)",
                "probes": [
                    {
                        "id": "mcp-keys",
                        "method": "json-keys",
                        "path": "mcp/marker.json",
                        "required": ["component", "healthy"],
                        "command": "json-keys:mcp/marker.json",
                    }
                ],
            },
            {
                "id": "router.responding",
                "component": "router",
                "title": "Router present on disk but hash disagrees with expected",
                "probes": [
                    {
                        "id": "router-stat",
                        "method": "file-stat",
                        "path": "router/marker.json",
                        "min_bytes": 8,
                        "command": "file-stat:router/marker.json",
                    },
                    {
                        "id": "router-hash",
                        "method": "content-hash",
                        "path": "router/marker.json",
                        "sha256": WRONG_HASH,
                        "command": "content-hash:router/marker.json",
                    },
                ],
            },
            {
                "id": "cache.valid",
                "component": "cache",
                "title": "Cache marker missing — both independent probes fail",
                "probes": [
                    {
                        "id": "cache-stat",
                        "method": "file-stat",
                        "path": "cache/marker.json",
                        "min_bytes": 8,
                        "command": "file-stat:cache/marker.json",
                    },
                    {
                        "id": "cache-hash",
                        "method": "content-hash",
                        "path": "cache/marker.json",
                        "sha256": sha256_bytes(LEDGER),
                        "command": "content-hash:cache/marker.json",
                    },
                ],
            },
            {
                "id": "deploy.in_sync",
                "component": "deploy",
                "title": "Deploy tree present and byte-authentic (second positive control)",
                "probes": [
                    {
                        "id": "deploy-stat",
                        "method": "file-stat",
                        "path": "deploy/marker.json",
                        "min_bytes": 8,
                        "command": "file-stat:deploy/marker.json",
                    },
                    {
                        "id": "deploy-hash",
                        "method": "content-hash",
                        "path": "deploy/marker.json",
                        "sha256": sha256_bytes(DEPLOY),
                        "command": "content-hash:deploy/marker.json",
                    },
                ],
            },
        ],
    }
    INVENTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    INVENTORY_PATH.write_text(
        json.dumps(inventory, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    return inventory
