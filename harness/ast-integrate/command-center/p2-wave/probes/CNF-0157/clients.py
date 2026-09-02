#!/usr/bin/env python3
"""Declared supported clients and live version capture from the client binary.

Version strings come from the client CLI. Documentation and catalog text are
never used as a version source. An absent binary is NOT-CHECKED, never PASS.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

CLAIMS = (
    ("plugin", "Plugin package loads and is recognized by the client adapter"),
    ("hook", "Hooks actually execute a side-effect, not merely a settings key"),
    ("skill", "Installed skill.council is selected by the router"),
    ("mcp-adapter", "MCP adapter lists the fixture matrix-echo tool"),
)

# Declared set from the compatibility-matrix contract cited by BLD-0006 / CNF-0157.
# Cursor Agent on this box is recorded as an extra undeclared runtime, never
# folded into Claude Code or into a PASS for a missing declared client.
DECLARED_CLIENTS: tuple[dict[str, Any], ...] = (
    {
        "id": "claude-code",
        "display": "Claude Code",
        "binaries": ("claude", "claude-code"),
        "version_args": (("--version",), ("-v",), ("version",)),
        "install_prerequisite": (
            "Install Anthropic Claude Code CLI so `claude --version` succeeds on PATH."
        ),
        "catalog_token": "Claude Code",
    },
    {
        "id": "codex-cli",
        "display": "Codex CLI",
        "binaries": ("codex",),
        "version_args": (("--version",), ("-v",), ("version",)),
        "install_prerequisite": (
            "Install OpenAI Codex CLI so `codex --version` succeeds on PATH."
        ),
        "catalog_token": "Codex CLI",
    },
    {
        "id": "antigravity",
        "display": "Antigravity/agy",
        "binaries": ("agy", "antigravity"),
        "version_args": (("--version",), ("-v",), ("version",)),
        "install_prerequisite": (
            "Install Antigravity/agy so `agy --version` or `antigravity --version` succeeds on PATH."
        ),
        "catalog_token": "Antigravity/agy",
    },
    {
        "id": "mcp-generic",
        "display": "generic MCP host",
        "binaries": ("mcp", "mcp-inspector", "modelcontextprotocol"),
        "version_args": (("--version",), ("-v",), ("version",)),
        "install_prerequisite": (
            "Install a generic MCP host named by the compatibility matrix "
            "(`mcp` / MCP inspector) on PATH. Cursor Agent is a distinct undeclared "
            "runtime and is not used as a stand-in for this cell."
        ),
        "catalog_token": "generic MCP host",
    },
)

# Marker files that mean a *client-loadable* plugin package is installed.
# `tools/plugin` as a directory is not enough: other units ship a Python
# cache/JSON toolkit at that path (cli.py, strict_json.py, cache_ownership.py)
# with no plugin.json hooks/skills/mcp adapter tree.
PRODUCTION_PACKAGE_FILES = (
    ".claude-plugin/plugin.json",
    ".claude-plugin/marketplace.json",
    "plugin.json",
    "hooks/hooks.json",
)
CLIENT_PLUGIN_MANIFEST_KEYS = ("name", "hooks", "skills", "mcp")

FORBIDDEN_VERSION_SOURCES = frozenset(
    {
        "documentation",
        "catalog",
        "guessed",
        "hardcoded",
        "path-inference",
        "package.json",
    }
)
ALLOWED_VERSION_SOURCES = frozenset(
    {
        "not-installed",
        "client-cli",
        "client-cli-unreadable",
        "adapter-fixture",
    }
)

EXTRA_RUNTIME_BINARIES = ("cursor-agent", "agent")


def catalog_declares_supported_set(repo: Path | None = None) -> dict[str, Any]:
    """Second signal: the catalog text names the declared clients (not a typed table)."""
    root = repo or REPO
    catalog = root / "command-center" / "WORK-UNIT-CATALOG.json"
    text = catalog.read_text(encoding="utf-8")
    missing = [
        spec["catalog_token"]
        for spec in DECLARED_CLIENTS
        if spec["catalog_token"] not in text
    ]
    return {
        "path": "command-center/WORK-UNIT-CATALOG.json",
        "tokens_present": missing == [],
        "missing_tokens": missing,
        "note": (
            "Supported-client list is taken from the BLD-0006 / CNF-0157 catalog "
            "citation. A filled Phase-4 compatibility matrix file is not in this "
            "worktree; absence is reported, not inferred as an all-green matrix."
        ),
    }


def _first_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:240]
    return ""


def _run_version(executable: str, args: tuple[str, ...]) -> dict[str, Any] | None:
    try:
        proc = subprocess.run(
            [executable, *args],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    blob = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
    head = _first_line(blob)
    if proc.returncode != 0 or not head:
        return None
    return {
        "installed": True,
        "executable": executable,
        "version": head,
        "version_source": "client-cli",
        "version_command": [executable, *args],
        "raw_head": head,
    }


def probe_binary(spec: dict[str, Any]) -> dict[str, Any]:
    """Read version from the client itself. Never invent a version."""
    found_exe = None
    for name in spec["binaries"]:
        exe = shutil.which(name)
        if exe:
            found_exe = exe
            for args in spec["version_args"]:
                hit = _run_version(exe, args)
                if hit:
                    hit["client_id"] = spec["id"]
                    hit["display"] = spec["display"]
                    hit["install_prerequisite"] = spec["install_prerequisite"]
                    hit["which"] = name
                    return hit
            break
    if found_exe:
        return {
            "client_id": spec["id"],
            "display": spec["display"],
            "installed": True,
            "executable": found_exe,
            "version": None,
            "version_source": "client-cli-unreadable",
            "version_command": [found_exe, "--version"],
            "install_prerequisite": (
                spec["install_prerequisite"]
                + " Binary is on PATH but --version did not yield a parseable string."
            ),
            "which": Path(found_exe).name,
        }
    return {
        "client_id": spec["id"],
        "display": spec["display"],
        "installed": False,
        "executable": None,
        "version": None,
        "version_source": "not-installed",
        "version_command": None,
        "install_prerequisite": spec["install_prerequisite"],
        "which": None,
    }


def extra_runtimes() -> list[dict[str, Any]]:
    """Runtimes present on the box that are not declared supported clients."""
    rows = []
    seen: set[str] = set()
    for name in EXTRA_RUNTIME_BINARIES:
        exe = shutil.which(name)
        if not exe:
            continue
        resolved = str(Path(exe).resolve())
        if resolved in seen:
            continue
        seen.add(resolved)
        hit = None
        for args in (("--version",), ("-v",)):
            hit = _run_version(exe, args)
            if hit:
                break
        rows.append(
            {
                "name": name,
                "executable": exe,
                "resolved": resolved,
                "declared_supported_client": False,
                "folded_into_matrix_pass": False,
                "version": None if hit is None else hit["version"],
                "version_source": "not-installed" if hit is None else hit["version_source"],
                "note": (
                    "Observed extra runtime. Not a declared supported client "
                    "(Claude Code / Codex CLI / Antigravity/agy / generic MCP host). "
                    "Not used to mark any declared-client cell REPRODUCES."
                ),
            }
        )
    return rows


def _manifest_is_client_plugin(path: Path) -> bool:
    """True only for a client-loadable plugin.json (hooks/skills/mcp)."""
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return False
    if not isinstance(doc, dict):
        return False
    return all(key in doc for key in CLIENT_PLUGIN_MANIFEST_KEYS)


def _adjacent_tools_plugin(root: Path) -> dict[str, Any]:
    """Classify tools/plugin: Python toolkit vs loadable adapter package."""
    directory = root / "tools/plugin"
    manifest = directory / "plugin.json"
    files: list[str] = []
    if directory.is_dir():
        files = sorted(
            child.name
            for child in directory.iterdir()
            if child.is_file() and child.suffix in {".py", ".json"}
        )
    loadable = directory.is_dir() and manifest.is_file() and _manifest_is_client_plugin(
        manifest
    )
    if not directory.is_dir():
        note = "tools/plugin directory is absent."
    elif loadable:
        note = (
            "tools/plugin contains a client-loadable plugin.json "
            "(hooks/skills/mcp). That is the production adapter package."
        )
    else:
        note = (
            "tools/plugin is a Python cache/JSON toolkit "
            "(strict_json, cache_ownership, cli). It is not the "
            "client-loadable plugin package: no plugin.json with "
            "hooks/skills/mcp. Not used to mark live cells REPRODUCES."
        )
    return {
        "path": "tools/plugin",
        "exists": directory.is_dir(),
        "plugin_json_present": manifest.is_file(),
        "is_loadable_plugin_package": loadable,
        "files": files,
        "note": note,
    }


def production_plugin_package(repo: Path | None = None) -> dict[str, Any]:
    root = repo or REPO
    present = []
    absent = []
    for rel in PRODUCTION_PACKAGE_FILES:
        path = root / rel
        if path.exists():
            present.append(rel)
        else:
            absent.append(rel)
    adjacent = _adjacent_tools_plugin(root)
    if adjacent["is_loadable_plugin_package"]:
        present.append("tools/plugin")
    elif not adjacent["exists"]:
        absent.append("tools/plugin")
    fixture = HERE / "fixtures" / "plugin" / "plugin.json"
    production_present = bool(present)
    if production_present:
        note = (
            "A client-loadable production plugin marker is on disk. That is "
            "not in-client proof: live-client cells stay NOT-CHECKED unless "
            "the declared client binary actually loaded the package. "
            "Adapter-fixture cells still use the non-author harness."
        )
    else:
        note = (
            "Client-loadable production plugin package and adapter layer "
            "(.claude-plugin/plugin.json, marketplace.json, repo-root "
            "plugin.json, hooks/hooks.json, tools/plugin/plugin.json with "
            "hooks/skills/mcp) are absent. tools/plugin may exist as a "
            "Python toolkit without being that package. Adapter-fixture "
            "cells exercise a non-author reproduction harness. Live-client "
            "cells stay NOT-CHECKED for in-client load."
        )
    return {
        "production_present": production_present,
        "production_paths_present": present,
        "production_paths_absent": absent,
        "adjacent_tools_plugin": adjacent,
        "fixture_plugin_json": "command-center/p2-wave/probes/CNF-0157/fixtures/plugin/plugin.json",
        "fixture_present": fixture.is_file(),
        "note": note,
    }


def discover(repo: Path | None = None) -> dict[str, Any]:
    root = repo or REPO
    clients = [probe_binary(spec) for spec in DECLARED_CLIENTS]
    return {
        "catalog": catalog_declares_supported_set(root),
        "plugin_package": production_plugin_package(root),
        "clients": clients,
        "installed_declared": [c["client_id"] for c in clients if c["installed"]],
        "missing_declared": [c["client_id"] for c in clients if not c["installed"]],
        "extra_runtimes": extra_runtimes(),
    }


def client_by_id(discovery: dict[str, Any], client_id: str) -> dict[str, Any]:
    for row in discovery["clients"]:
        if row["client_id"] == client_id:
            return row
    raise KeyError(client_id)


if __name__ == "__main__":
    print(json.dumps(discover(), indent=2, sort_keys=True))
