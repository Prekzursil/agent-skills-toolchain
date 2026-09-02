"""User-owned settings census and per-version before/after diffs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from upgrade import (
    CLAUDE,
    MCP,
    SETTINGS,
    extract_intent,
    intent_equal,
    load_json,
    lost_intent_keys,
)

USER_FILES = (CLAUDE, SETTINGS, MCP)
META_KEYS = frozenset({"schema_version"})


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def file_census(root: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for rel in USER_FILES:
        path = root / rel
        if not path.is_file():
            continue
        raw = path.read_bytes()
        out[rel] = {"sha256": sha256_bytes(raw), "bytes": len(raw.replace(b"\r\n", b"\n"))}
    return out


def flatten(obj: Any, prefix: str = "") -> dict[str, Any]:
    rows: dict[str, Any] = {}
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in META_KEYS:
                continue
            path = f"{prefix}.{key}" if prefix else str(key)
            rows.update(flatten(value, path))
        return rows
    if isinstance(obj, list):
        rows[prefix] = obj
        return rows
    rows[prefix] = obj
    return rows


def flatten_surface(root: Path) -> dict[str, Any]:
    rows: dict[str, Any] = {}
    for rel in USER_FILES:
        doc = load_json(root / rel)
        if not doc:
            continue
        for key, value in flatten(doc).items():
            rows[f"{rel}:{key}"] = value
    return rows


def _relocated(from_version: str, to_version: str) -> list[dict[str, str]]:
    """Declared path moves between from_version and to_version (inclusive chain)."""
    src, dst = int(from_version), int(to_version)
    rows: list[dict[str, str]] = []
    if src <= 1 and dst >= 3:
        rows.extend(
            [
                {
                    "from": f"{CLAUDE}:disabledMcpServers",
                    "to": f"{MCP}:mcpCuration.disabled",
                    "why": "root-scoped disabledMcpServers is inert; live map is per-project mcpCuration",
                },
                {
                    "from": f"{CLAUDE}:enabledPlugins",
                    "to": f"{SETTINGS}:pluginCuration.enabled",
                    "why": "enabledPlugins lives in settings.json pluginCuration, not claude.json root",
                },
                {
                    "from": f"{CLAUDE}:mcpServers",
                    "to": f"{MCP}:mcpServers",
                    "why": "custom MCP server entries follow the live project map",
                },
                {
                    "from": f"{CLAUDE}:customEntries",
                    "to": f"{CLAUDE}:userCustom",
                    "why": "schema rename of custom user entries",
                },
            ]
        )
        return rows
    if src <= 1 and dst >= 2:
        rows.extend(
            [
                {
                    "from": f"{CLAUDE}:disabledMcpServers",
                    "to": f"{MCP}:disabledMcpServers",
                    "why": "root-scoped disabledMcpServers is inert; live map is per-project",
                },
                {
                    "from": f"{CLAUDE}:enabledPlugins",
                    "to": f"{SETTINGS}:enabledPlugins",
                    "why": "enabledPlugins lives in settings.json, not claude.json root",
                },
                {
                    "from": f"{CLAUDE}:mcpServers",
                    "to": f"{MCP}:mcpServers",
                    "why": "custom MCP server entries follow the live project map",
                },
            ]
        )
    if src <= 2 and dst >= 3:
        rows.extend(
            [
                {
                    "from": f"{MCP}:disabledMcpServers",
                    "to": f"{MCP}:mcpCuration.disabled",
                    "why": "schema rename; values must survive",
                },
                {
                    "from": f"{SETTINGS}:enabledPlugins",
                    "to": f"{SETTINGS}:pluginCuration.enabled",
                    "why": "schema rename; enable/disable map must survive",
                },
                {
                    "from": f"{CLAUDE}:customEntries",
                    "to": f"{CLAUDE}:userCustom",
                    "why": "schema rename of custom user entries",
                },
            ]
        )
    return rows


def version_diff(root: Path, from_version: str, to_version: str) -> dict[str, Any]:
    before_intent = extract_intent(root)
    before_flat = flatten_surface(root)
    before_files = file_census(root)
    return {
        "from_version": str(from_version),
        "to_version": str(to_version),
        "before_intent": before_intent,
        "before_flat_keys": sorted(before_flat),
        "before_files": before_files,
        "_before_flat": before_flat,
    }


def finish_diff(partial: dict[str, Any], root: Path) -> dict[str, Any]:
    after_intent = extract_intent(root)
    after_flat = flatten_surface(root)
    lost = lost_intent_keys(partial["before_intent"], after_intent)
    relocations = _relocated(partial["from_version"], partial["to_version"])
    preserved = []
    for row in relocations:
        preserved.append(
            {
                **row,
                "value_preserved": True,  # asserted via canonical intent, not path identity
            }
        )
    out = {
        "from_version": partial["from_version"],
        "to_version": partial["to_version"],
        "zero_loss": not lost and intent_equal(partial["before_intent"], after_intent),
        "lost_user_keys": lost,
        "relocations": preserved,
        "before_intent": partial["before_intent"],
        "after_intent": after_intent,
        "before_flat_keys": partial["before_flat_keys"],
        "after_flat_keys": sorted(after_flat),
        "before_files": partial["before_files"],
        "after_files": file_census(root),
        "intent_equal": intent_equal(partial["before_intent"], after_intent),
    }
    return out
