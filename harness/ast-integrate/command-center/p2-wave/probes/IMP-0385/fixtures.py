"""Shared fixture paths and expected ids for IMP-0385 probes."""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
SIX_ROOTS = HERE / "fixtures" / "six-roots"
CENSUS_PS1 = HERE / "census.ps1"

KNOWN_PRESENT = "skill:claude_skills:present-skill/SKILL.md"
KNOWN_ABSENT = "skill:claude_skills:absent-sentinel/SKILL.md"

EXPECTED_KINDS = ("skill", "plugin", "command", "workflow", "hook", "mcp_tool")


def fixture_roots() -> dict[str, Path]:
    return {
        "claude_skills": SIX_ROOTS / "claude_skills",
        "agents_skills": SIX_ROOTS / "agents_skills",
        "claude_plugins": SIX_ROOTS / "claude_plugins",
        "claude_commands": SIX_ROOTS / "claude_commands",
        "repo_skills": SIX_ROOTS / "repo_skills",
        "repo_workflows": SIX_ROOTS / "repo_workflows",
    }
