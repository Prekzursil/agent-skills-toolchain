"""Live tool inventory for this Linux box (session tools + on-disk + PATH)."""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

from common import INVENTORY_PATH, REPO, UNIT_ID, dump_json, sha256_file

# Agent shells prepend cursor-agent/versions/... which ships rg/node. Supervisor
# remasure does not. Resolve CLIs against OS directories so the catalog size is
# the box, not the current process PATH.
OS_CLI_PATH = "/usr/local/bin:/usr/bin:/bin"

# Captured from this Cursor agent session on 2026-08-24 (first-party + dynamic).
# These are the tools actually exposed to the agent running this unit.
SESSION_TOOLS: list[dict[str, str]] = [
    {
        "name": "Shell",
        "source": "session-first-party",
        "description": (
            "Execute a shell command in a bash session. Use for running programs, "
            "git, python, and OS commands. Not for reading a known file path."
        ),
    },
    {
        "name": "Grep",
        "source": "session-first-party",
        "description": (
            "Search file contents with ripgrep-style regex. Returns matching lines. "
            "Not a filename globber."
        ),
    },
    {
        "name": "Glob",
        "source": "session-first-party",
        "description": (
            "Find files by glob pattern such as **/*.py. Returns paths, not contents."
        ),
    },
    {
        "name": "Read",
        "source": "session-first-party",
        "description": (
            "Read a file from the local filesystem as UTF-8 text, optionally with "
            "line offset and limit. Use when the path is already known."
        ),
    },
    {
        "name": "Delete",
        "source": "session-first-party",
        "description": "Delete a file at a specified path. Fails if the file does not exist.",
    },
    {
        "name": "WebSearch",
        "source": "session-first-party",
        "description": (
            "Search the public web for a query. Returns snippets and URLs, not a full page."
        ),
    },
    {
        "name": "WebFetch",
        "source": "session-first-party",
        "description": (
            "Fetch a specified URL and return its contents as readable markdown."
        ),
    },
    {
        "name": "Write",
        "source": "session-first-party",
        "description": "Write a file to the local filesystem, creating or overwriting it.",
    },
    {
        "name": "StrReplace",
        "source": "session-first-party",
        "description": (
            "Perform exact string replacements in files. Use for surgical in-file edits."
        ),
    },
    {
        "name": "EditNotebook",
        "source": "session-first-party",
        "description": "Edit a jupyter notebook cell. Not a general file editor.",
    },
    {
        "name": "TodoWrite",
        "source": "session-first-party",
        "description": "Create and manage a structured task list for this coding session.",
    },
    {
        "name": "ReadLints",
        "source": "session-first-party",
        "description": "Read and display linter errors from the current workspace.",
    },
    {
        "name": "Task",
        "source": "session-first-party",
        "description": "Launch a specialized subagent to handle a complex multi-step task.",
    },
    {
        "name": "AwaitShell",
        "source": "session-first-party",
        "description": "Check or poll a backgrounded shell job until it completes or matches a pattern.",
    },
    {
        "name": "GetDynamicTools",
        "source": "session-first-party",
        "description": "Discover tools available through dynamic namespaces such as MCP servers.",
    },
    {
        "name": "FetchMcpResource",
        "source": "session-first-party",
        "description": "Read a specific resource from an MCP server by server name and URI.",
    },
    {
        "name": "SwitchMode",
        "source": "session-first-party",
        "description": "Switch the interaction mode to plan or agent.",
    },
    {
        "name": "CallDynamicTool",
        "source": "session-first-party",
        "description": "Invoke one tool from a dynamic namespace after discovering its schema.",
    },
    {
        "name": "AskQuestion",
        "source": "session-first-party",
        "description": "Collect structured multiple-choice answers from the user.",
    },
    {
        "name": "cursor.CreateGoal",
        "source": "session-dynamic",
        "description": "Create a goal. Only when explicitly requested.",
    },
    {
        "name": "cursor.GenerateImage",
        "source": "session-dynamic",
        "description": "Generate an image file from a text description when the user asks for an image.",
    },
    {
        "name": "cursor.UpdateGoal",
        "source": "session-dynamic",
        "description": "Update an existing goal status. Set complete only when the objective is achieved.",
    },
]

ESTATE_PACKAGES: list[tuple[str, str, str]] = [
    (
        "agentspec",
        "tools/agentspec/agentspec/spec.py",
        "Frozen AgentSpec workflow node types (WorkUnit, UnitTemplate, FanOut).",
    ),
    (
        "council",
        "tools/council/__init__.py",
        "Council runtime package. Submodules land as later IMP units close.",
    ),
    (
        "blueprint_conformance",
        "tools/blueprint_conformance/__init__.py",
        "Blueprint conformance harness. Discovers library entries from the registry file.",
    ),
    (
        "workflows",
        "tools/workflows/__init__.py",
        "Workflow catalog helpers including IMP-0204 retirement.",
    ),
    (
        "release",
        "tools/release/__init__.py",
        "Release-time gates evaluated against built artifacts, not the source tree.",
    ),
    (
        "marketplace",
        "tools/marketplace/__init__.py",
        "Marketplace registry tooling: integrity sweep and blob store substrate.",
    ),
    (
        "command-center",
        "tools/command-center/catalog.py",
        "Command-center catalog: load, save, and derive the work-unit dependency graph.",
    ),
    (
        "unit_manifest",
        "tools/command-center/unit_manifest.py",
        "Produce and verify the dedicated completion-condition-11 unit manifest.",
    ),
]

PATH_CLIS: list[tuple[str, str]] = [
    ("python3", "CPython interpreter on PATH"),
    ("git", "Git version control CLI"),
    ("jq", "jq JSON processor CLI"),
    ("rg", "ripgrep content search CLI"),
    ("node", "Node.js JavaScript runtime"),
]

def _home() -> Path:
    raw = (os.environ.get("HOME") or str(Path.home())).replace("\r", "").replace("\n", "")
    return Path(raw)


def _mcp_candidates() -> list[Path]:
    home = _home()
    return [
        home / ".mcp.json",
        home / ".cursor" / "mcp.json",
        home / ".claude.json",
        REPO / ".mcp.json",
        REPO / ".cursor" / "mcp.json",
    ]


def _os_which(name: str) -> str | None:
    return shutil.which(name, path=OS_CLI_PATH)


def _tool(name: str, source: str, description: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    row: dict[str, Any] = {
        "name": name,
        "source": source,
        "description": description,
    }
    if extra:
        row.update(extra)
    return row


def collect_inventory() -> dict[str, Any]:
    tools: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(row: dict[str, Any]) -> None:
        name = row["name"]
        if name in seen:
            return
        seen.add(name)
        tools.append(row)

    for row in SESSION_TOOLS:
        add(dict(row))

    for name, rel, desc in ESTATE_PACKAGES:
        path = REPO / rel
        extra = {"path": rel, "present_on_disk": path.is_file()}
        if path.is_file():
            add(_tool(name, "estate-package", desc, extra))

    path_hits: list[dict[str, Any]] = []
    for name, desc in PATH_CLIS:
        resolved = _os_which(name)
        path_hits.append({"name": name, "which": resolved})
        if resolved:
            add(_tool(name, "path-cli", desc, {"which": resolved}))

    mcp_found: list[dict[str, Any]] = []
    for cand in _mcp_candidates():
        mcp_found.append({"path": str(cand), "exists": cand.is_file()})
        if cand.is_file():
            add(
                _tool(
                    f"mcp-config:{cand.name}",
                    "mcp-config-file",
                    f"MCP configuration file at {cand}",
                    {"path": str(cand)},
                )
            )

    tools.sort(key=lambda t: t["name"])
    doc = {
        "unit_id": UNIT_ID,
        "captured_at": "live-os-cli-path",
        "host": "linux",
        "worktree": str(REPO),
        "mcp_config_candidates": mcp_found,
        "path_cli_resolution": path_hits,
        "tool_count": len(tools),
        "tools": tools,
        "sources": sorted({t["source"] for t in tools}),
        "note": (
            "Session tools are the live agent-exposed fleet for this unit. "
            "Estate packages are on-disk under tools/. PATH CLIs are resolved "
            "with shutil.which against /usr/local/bin:/usr/bin:/bin so "
            "agent-injected PATH (cursor-agent bundled rg/node) cannot change "
            "catalog size between delivery and remasure. "
            "No MCP server JSON was assumed; candidate paths were probed."
        ),
    }
    return doc


def write_inventory() -> dict[str, Any]:
    doc = collect_inventory()
    dump_json(INVENTORY_PATH, doc)
    digest = sha256_file(INVENTORY_PATH)
    doc["inventory_sha256"] = digest
    return doc


if __name__ == "__main__":
    d = write_inventory()
    print(f"inventory tools={d['tool_count']} sha256={d['inventory_sha256']}")
