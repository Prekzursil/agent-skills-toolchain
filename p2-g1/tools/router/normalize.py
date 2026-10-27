"""Capability-record normalizer (IMP-0386)."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

FORMAT_SKILL_MD = "skill_md"
FORMAT_PLUGIN_JSON = "plugin_json"
FORMAT_WORKFLOW_HEADER = "workflow_header"
FORMAT_MCP_TOOL = "mcp_tool"

PLANTED_KEYS = {
    FORMAT_SKILL_MD: "planted_extra_skill",
    FORMAT_PLUGIN_JSON: "planted_extra_plugin",
    FORMAT_WORKFLOW_HEADER: "planted_extra_workflow",
    FORMAT_MCP_TOOL: "planted_extra_mcp",
}

NATIVE_DROPS = {
    FORMAT_SKILL_MD: ("license", "allowed-tools", "compatibility", "metadata"),
    FORMAT_PLUGIN_JSON: ("keywords", "author", "homepage", "repository", "skills", "commands", "hooks"),
    FORMAT_WORKFLOW_HEADER: ("stages", "stopping"),
    FORMAT_MCP_TOOL: ("inputSchema", "annotations"),
}

LOSSLESS = ("name", "description")


@dataclass
class Parsed:
    source_format: str
    path: Path
    mapping: dict[str, Any]
    locators: dict[str, str] = field(default_factory=dict)


@dataclass
class NormalizationResult:
    parsed: Parsed
    record: dict[str, Any]
    dropped: list[dict[str, str]]


def lossless_keymap() -> dict[str, dict[str, str]]:
    return {
        FORMAT_MCP_TOOL: {"description": "description", "name": "name"},
        FORMAT_PLUGIN_JSON: {
            "description": "description",
            "keywords": "keywords",
            "name": "name",
            "version": "version",
        },
        FORMAT_SKILL_MD: {
            "description": "description",
            "license": "license",
            "name": "name",
            "paths": "paths",
            "version": "version",
        },
        FORMAT_WORKFLOW_HEADER: {
            "description": "description",
            "id": "id",
            "name": "name",
            "version": "version",
        },
    }


def detect_format(path: Path) -> str:
    name = path.name.lower()
    if name == "skill.md":
        return FORMAT_SKILL_MD
    if name == "plugin.json":
        return FORMAT_PLUGIN_JSON
    if name.endswith(".py"):
        return FORMAT_WORKFLOW_HEADER
    return FORMAT_MCP_TOOL


def _locator(path: Path, repo: Path | None, key: str, lines: list[str]) -> str:
    rel = path.as_posix()
    if repo:
        try:
            rel = path.resolve().relative_to(Path(repo).resolve()).as_posix()
        except ValueError:
            rel = path.as_posix()
    for i, line in enumerate(lines, 1):
        if key in line:
            return f"{rel}:{i}"
    return f"{rel}:1"


def parse_file(path: Path, repo: Path | None = None) -> Parsed:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    fmt = detect_format(path)
    mapping: dict[str, Any] = {}
    if fmt == FORMAT_SKILL_MD:
        fm = re.search(r"^---\n(.*?)\n---", text, re.S)
        body = fm.group(1) if fm else ""
        for raw in body.splitlines():
            if ":" in raw:
                k, _, v = raw.partition(":")
                mapping[k.strip()] = v.strip().strip('"')
    elif fmt == FORMAT_WORKFLOW_HEADER:
        for raw in lines:
            if ":" in raw and not raw.startswith("def ") and not raw.startswith("import"):
                k, _, v = raw.partition(":")
                key = k.strip().lstrip("# ").strip()
                if key and not key.startswith('"'):
                    mapping[key] = v.strip()
    else:
        mapping = json.loads(text)
    locators = {k: _locator(path, repo, k, lines) for k in mapping}
    return Parsed(source_format=fmt, path=path, mapping=mapping, locators=locators)


def source_lossless_projection(mapping: dict[str, Any], fmt: str) -> dict[str, Any]:
    return {k: mapping.get(k) for k in LOSSLESS if k in mapping}


def normalize_parsed(parsed: Parsed) -> NormalizationResult:
    rec = {
        "name": parsed.mapping.get("name"),
        "description": parsed.mapping.get("description"),
        "capability_id": str(parsed.mapping.get("id") or parsed.mapping.get("name") or parsed.path.stem),
        "source_format": parsed.source_format,
    }
    dropped = []
    planted = PLANTED_KEYS[parsed.source_format]
    natives = NATIVE_DROPS[parsed.source_format]
    for key in list(parsed.mapping):
        if key in LOSSLESS or key in {"id", "version"}:
            continue
        if key == planted or key in natives:
            dropped.append(
                {
                    "source_key": key,
                    "source_format": parsed.source_format,
                    "locator": parsed.locators.get(key) or f"{parsed.path.as_posix()}:1",
                    "why": "lossy-register",
                }
            )
    return NormalizationResult(parsed=parsed, record=rec, dropped=dropped)


def normalize_file(path: Path, repo: Path | None = None) -> NormalizationResult:
    return normalize_parsed(parse_file(Path(path), repo=repo))


def roundtrip_errors(parsed: Parsed, result: NormalizationResult) -> list[str]:
    src = source_lossless_projection(parsed.mapping, parsed.source_format)
    errs = []
    for k, v in src.items():
        if result.record.get(k) != v:
            errs.append(f"lossy {k}: {result.record.get(k)!r} != {v!r}")
    return errs


def planted_errors(parsed: Parsed, result: NormalizationResult, planted: str) -> list[str]:
    keys = {row["source_key"] for row in result.dropped}
    if planted in parsed.mapping and planted not in keys:
        return [f"planted {planted} not registered"]
    return []
