#!/usr/bin/env python
"""Regression suite: the deployable CLAUDE.md must name the SAME user-scope config file
that the code resolves.

Defect pinned (C46 / D-a152). ``agent-self/config/CLAUDE.md`` is copied verbatim to
``~/.claude`` by ``agent-self/bootstrap.ps1``, so its setup comments are operator
instructions, not prose. Next to ``claude mcp add --scope user codex -- codex
mcp-server`` it said:

    # Mounts the official OpenAI MCP at ~/.claude/settings.json

Every other authority in the repo disagrees: ``tools/mcpctl/mcpctl/sources.py`` resolves
the user config to ``~/.claude.json``, ``tools/mcpctl/mcpctl/topology.py`` builds user MCP
topology from that document's ``mcpServers`` member, and ``agent-self/bootstrap.ps1``
tells the operator to merge user MCP servers into ``~/.claude.json`` while explicitly
leaving it untouched. An operator following the comment inspects a file that holds
permissions and plugin enablement but no MCP registration -- so a working registration
reads as absent, and a backup scoped to the documented file misses it.

KNOWN-BROKEN CONTROL IS MANDATORY: ``PRE_FIX_COMMENT`` is the byte-exact pre-fix line and
the predicate is asserted to trip on it.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DEPLOY_CLAUDE_MD = REPO / "agent-self" / "config" / "CLAUDE.md"
SOURCES = REPO / "tools" / "mcpctl" / "mcpctl" / "sources.py"
BOOTSTRAP = REPO / "agent-self" / "bootstrap.ps1"

PRE_FIX_COMMENT = "# Mounts the official OpenAI MCP at ~/.claude/settings.json"

# "the user-scope MCP registration lives in settings.json" -- the false claim. Matches a
# settings.json path that is NOT immediately negated (NOT / not / never / rather than).
_MCP_IN_SETTINGS = re.compile(
    r"(?<!not )(?<!NOT )(?<!never )~/\.claude/settings\.json", re.IGNORECASE
)


def _offending_lines(text: str) -> list[str]:
    """Lines that point an MCP/`mcp add` instruction at ~/.claude/settings.json."""
    out = []
    for line in text.splitlines():
        if not _MCP_IN_SETTINGS.search(line):
            continue
        low = line.lower()
        if "mcp" in low and not any(
            neg in line
            for neg in ("NOT ~/.claude/settings.json", "not ~/.claude/settings.json")
        ):
            out.append(line.strip())
    return out


# ----------------------------------------------------------------------------------
# controls -- prove the predicate can SEE the defect, and does not over-fire
# ----------------------------------------------------------------------------------
def test_control_detector_fires_on_pre_fix_comment() -> None:
    assert _offending_lines(PRE_FIX_COMMENT) == [PRE_FIX_COMMENT], (
        "detector is vacuous: it did not flag the byte-exact pre-fix line, so a clean "
        "live result proves nothing"
    )


def test_control_detector_accepts_the_corrected_wording() -> None:
    corrected = (
        '# Writes the registration into the "mcpServers" object of ~/.claude.json '
        "(the user-scope\n# config), NOT ~/.claude/settings.json — settings.json only "
        "carries permissions/plugins."
    )
    assert _offending_lines(corrected) == []


def test_control_detector_ignores_non_mcp_settings_mentions() -> None:
    assert _offending_lines("Permissions live in ~/.claude/settings.json.") == []


# ----------------------------------------------------------------------------------
# the live assertions
# ----------------------------------------------------------------------------------
def test_deploy_claude_md_does_not_point_mcp_setup_at_settings_json() -> None:
    text = DEPLOY_CLAUDE_MD.read_text(encoding="utf-8")
    bad = _offending_lines(text)
    assert not bad, (
        "agent-self/config/CLAUDE.md tells the operator the user-scope MCP registration "
        f"lives in ~/.claude/settings.json: {bad}. mcpctl resolves it to ~/.claude.json."
    )


def test_deploy_claude_md_names_claude_json_next_to_the_mcp_add_command() -> None:
    lines = DEPLOY_CLAUDE_MD.read_text(encoding="utf-8").splitlines()
    idx = [i for i, ln in enumerate(lines) if "mcp add --scope user codex" in ln]
    assert idx, "the `claude mcp add --scope user codex` setup block disappeared"
    window = "\n".join(lines[idx[0] : idx[0] + 6])
    assert "~/.claude.json" in window, (
        "the user-scope setup block no longer names ~/.claude.json within 5 lines of the "
        f"command, so the operator has no correct path to check:\n{window}"
    )


def test_code_authorities_still_resolve_user_config_to_claude_json() -> None:
    """The premise of the fix -- two independent, mechanically different anchors."""
    assert 'claude_json=home / ".claude.json"' in SOURCES.read_text(encoding="utf-8"), (
        "mcpctl/sources.py no longer resolves the user config to ~/.claude.json; "
        "re-derive the correct path before trusting this suite"
    )
    assert "~/.claude.json" in BOOTSTRAP.read_text(encoding="utf-8"), (
        "bootstrap.ps1 no longer names ~/.claude.json"
    )
