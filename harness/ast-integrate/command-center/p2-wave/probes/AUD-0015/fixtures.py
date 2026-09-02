"""Fixture estates for both-states scope control and leak-proof reader proof."""
from __future__ import annotations

import json
from pathlib import Path

from reader import PLANTED_SECRET

SERVER = "alpha"
CWD = "/opt/p2/ast-integrate"


def _write(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _base(root: Path) -> Path:
    root = Path(root)
    (root / "home" / ".claude").mkdir(parents=True, exist_ok=True)
    return root


def _mcp() -> dict:
    return {
        "mcpServers": {
            SERVER: {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
                "env": {"ANTHROPIC_API_KEY": PLANTED_SECRET},
            }
        }
    }


def _settings() -> dict:
    return {
        "model": "opus",
        "env": {
            "ANTHROPIC_API_KEY": PLANTED_SECRET,
            "OPENAI_API_KEY": PLANTED_SECRET,
        },
        "enabledMcpjsonServers": {SERVER: True},
        "permissions": {"allow": ["Read"]},
    }


def build_root_disabled(root: Path) -> Path:
    """Same server disabled only at ~/.claude.json ROOT (inert on this estate)."""
    root = _base(root)
    _write(root / "home" / ".mcp.json", _mcp())
    _write(
        root / "home" / ".claude.json",
        {
            "disabledMcpServers": [SERVER],
            "numStartups": 1,
            "projects": {CWD: {"enabledMcpjsonServers": {SERVER: True}}},
        },
    )
    _write(root / "home" / ".claude" / "settings.json", _settings())
    return root


def build_project_disabled(root: Path) -> Path:
    """Same server disabled in the per-project block (effective disable)."""
    root = _base(root)
    _write(root / "home" / ".mcp.json", _mcp())
    _write(
        root / "home" / ".claude.json",
        {
            "disabledMcpServers": [],
            "numStartups": 1,
            "projects": {
                CWD: {
                    "disabledMcpServers": [SERVER],
                    "mcpServers": {},
                }
            },
        },
    )
    _write(root / "home" / ".claude" / "settings.json", _settings())
    return root


def write_proc_fixture(root: Path, with_mcp: bool) -> Path:
    root = Path(root)
    (root / "1").mkdir(parents=True, exist_ok=True)
    (root / "1" / "cmdline").write_bytes(b"init\0")
    (root / "1" / "comm").write_text("init\n", encoding="utf-8")
    (root / "42").mkdir(parents=True, exist_ok=True)
    (root / "42" / "cmdline").write_bytes(b"bash\0")
    (root / "42" / "comm").write_text("bash\n", encoding="utf-8")
    if with_mcp:
        (root / "1101").mkdir(parents=True, exist_ok=True)
        (root / "1101" / "cmdline").write_bytes(
            b"npx\0-y\0@modelcontextprotocol/server-filesystem\0/tmp\0"
        )
        (root / "1101" / "comm").write_text("mcp-server-filesystem\n", encoding="utf-8")
        (root / "1102").mkdir(parents=True, exist_ok=True)
        (root / "1102" / "cmdline").write_bytes(
            b"node\0mcp-server-github\0--token\0sk-planted-not-real\0"
        )
        (root / "1102" / "comm").write_text("mcp-server-github\n", encoding="utf-8")
    return root
