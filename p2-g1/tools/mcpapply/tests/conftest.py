"""Shared hermetic fixtures.

NOTHING here touches the operator's real configuration, spawns a host session, or
opens a non-loopback socket. Every config document is synthesised under ``tmp_path``.

The ``live`` marker is default-deselected here as well as by ``-m "not live"`` in CI:
a bare ``pytest`` run on a developer box must not spawn a real host session either,
because ``mcp_toggle`` PERSISTS a write to the operator's own ``~/.claude.json``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path

import pytest
from mcpctl.sources import SourcePaths, load_sources, source_paths
from mcpctl.topology import Topology, build_topology

FIXED_NOW = datetime(2026, 7, 27, 3, 15, 0, tzinfo=timezone.utc)
STAMP = "20260727T031500Z"


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Deselect ``live`` unless it was asked for explicitly with ``-m``."""
    if "live" in (config.getoption("-m") or ""):
        return
    skip = pytest.mark.skip(reason="live: drives a REAL host session; run with -m live")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip)


#: A deliberately awkward inventory: an object-shaped denial, a project row whose key
#: is NOT an ancestor-substitutable prefix, an approved-but-disabled server, an
#: http server with no local process, and an env block holding a real-looking token.
CLAUDE_JSON: dict[str, object] = {
    "numStartups": 4211,
    "oauthAccount": {"emailAddress": "owner@example.invalid", "keep": "me"},
    "mcpServers": {
        "cloud-hub": {
            "type": "stdio",
            "command": "python",
            "args": ["-m", "cloud_hub"],
            # PLACEHOLDER, shaped so mcpctl's `xai-` redaction pattern matches it.
            "env": {"CLOUD_HUB_TOKEN": "xai-EXAMPLE-not-a-real-key", "EMPTY": ""},
        },
        "chrome-devtools": {"command": "npx", "args": ["chrome-devtools-mcp"]},
        "basic-memory": {"type": "http", "url": "http://127.0.0.1:8765/mcp"},
        "ghidra-mcp": {"command": "python", "args": ["-m", "ghidra_mcp"]},
    },
    "disabledMcpServers": ["ghidra-mcp"],
    "projects": {
        "C:/Users/Owner/source/proj": {
            "disabledMcpServers": ["chrome-devtools"],
            "history": [{"display": "keep this too"}],
        },
        "C:/Users/Owner": {"disabledMcpServers": ["cloud-hub", "basic-memory"]},
    },
}

MCP_JSON: dict[str, object] = {
    "mcpServers": {"playwright": {"command": "npx", "args": ["@playwright/mcp"]}},
    "someUnknownTopLevelKey": {"nested": [1, 2, 3]},
}

SETTINGS: dict[str, object] = {
    "deniedMcpServers": [{"serverName": "markitdown"}, {"serverName": "serena"}],
    "env": {"ENABLE_TOOL_SEARCH": "auto:5"},
}

SETTINGS_LOCAL: dict[str, object] = {
    "enabledMcpjsonServers": ["ghidra-mcp"],
    "enableAllProjectMcpServers": False,
}

DISABLED_DEFAULTS: dict[str, object] = {"disabledMcpServers": ["chrome-devtools"]}

PROJECT_KEY = "C:/Users/Owner/source/proj"


def write_home(root: Path, **overrides: object) -> SourcePaths:
    """Materialise the five scopes under ``root`` and return their paths."""
    docs: dict[str, object] = {
        "claude_json": overrides.get("claude_json", CLAUDE_JSON),
        "mcp_json": overrides.get("mcp_json", MCP_JSON),
        "settings": overrides.get("settings", SETTINGS),
        "settings_local": overrides.get("settings_local", SETTINGS_LOCAL),
        "disabled_defaults": overrides.get("disabled_defaults", DISABLED_DEFAULTS),
    }
    paths = source_paths(root)
    for label, path in paths.as_tuple():
        content = docs[label]
        if content is None:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(content, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    return paths


@pytest.fixture
def home(tmp_path: Path) -> Path:
    """A tmp_path home carrying the full five-scope fixture."""
    write_home(tmp_path)
    return tmp_path


@pytest.fixture
def paths(home: Path) -> SourcePaths:
    return source_paths(home)


@pytest.fixture
def top(paths: SourcePaths) -> Topology:
    docs, problems = load_sources(paths)
    assert problems == ()
    return build_topology(docs, project_key=PROJECT_KEY)


def topology_from(docs: Mapping[str, object], *, project_key: str | None) -> Topology:
    """Build a topology directly from in-memory documents."""
    from mcpctl.topology import SourceDocs

    return build_topology(
        SourceDocs(
            claude_json=docs.get("claude_json"),
            mcp_json=docs.get("mcp_json"),
            settings=docs.get("settings"),
            settings_local=docs.get("settings_local"),
            disabled_defaults=docs.get("disabled_defaults"),
        ),
        project_key=project_key,
    )
