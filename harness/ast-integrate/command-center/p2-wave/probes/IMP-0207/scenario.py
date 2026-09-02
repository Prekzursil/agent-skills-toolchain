"""Shared IMP-0207 fixtures: one workflow, narrowing vs widening presets."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"

WF_ID = "wf.demo.research"
PRESET_NARROW = "strict"
WORKFLOW_TOOLS = frozenset({"Read", "Grep", "Glob", "Bash"})
WORKFLOW_SOURCES = frozenset({"official-docs", "code", "papers"})
NARROW_TOOLS = frozenset({"Read", "Grep"})
NARROW_SOURCES = frozenset({"official-docs", "code"})
WIDEN_TOOL = "Write"
WIDEN_SOURCE = "public-tor"


def load_fixture(name: str) -> dict[str, Any]:
    path = FIXTURES / name
    return json.loads(path.read_text(encoding="utf-8"))


def pack_narrow() -> dict[str, Any]:
    return load_fixture("pack_narrow.json")


def pack_widen_tools() -> dict[str, Any]:
    return load_fixture("pack_widen_tools.json")


def pack_widen_source() -> dict[str, Any]:
    return load_fixture("pack_widen_source.json")


def pack_invalid_semver() -> dict[str, Any]:
    doc = pack_narrow()
    doc["version"] = "1.2"
    return doc


def pack_edited_widen() -> dict[str, Any]:
    """Editable narrowing preset mutated to request Write — must fail at reload."""
    doc = copy.deepcopy(pack_narrow())
    tools = list(doc["presets"][0]["tool_permissions"])
    tools.append(WIDEN_TOOL)
    doc["presets"][0]["tool_permissions"] = tools
    return doc
