"""Tests for core/paste_parse.py — parsing a pasted /mcp panel dump."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import paste_parse as pp  # noqa: E402

# A realistic /mcp panel dump (middle-dot separators + a 2-space variant).
PANEL = """Manage MCP servers
74 servers

apktool-mcp · ✔ connected · 16 tools
codecov · ✘ failed
hexstrike-ai · ◯ disabled
basic-memory   ✔ connected   42 tools
claude.ai Figma · ⚠ needs auth
> tavily · ✔ connected · 3 tools
[x] exa · ✔ connected

↑/↓ to navigate · Enter to view · esc to exit
"""


class TestParsePanel:
    def test_parses_expected_count(self):
        servers = pp.parse_mcp_panel(PANEL)
        names = [s.name for s in servers]
        assert names == [
            "apktool-mcp",
            "codecov",
            "hexstrike-ai",
            "basic-memory",
            "claude.ai Figma",
            "tavily",
            "exa",
        ]

    def test_connected_with_tools(self):
        s = pp.parse_mcp_panel(PANEL)[0]
        assert s.name == "apktool-mcp"
        assert s.state == pp.CONNECTED
        assert s.tool_count == 16

    def test_failed_no_tools(self):
        s = pp.parse_mcp_panel(PANEL)[1]
        assert s.state == pp.FAILED
        assert s.tool_count is None

    def test_disabled_state(self):
        s = pp.parse_mcp_panel(PANEL)[2]
        assert s.state == pp.DISABLED
        assert s.enabled is False

    def test_two_space_separator(self):
        s = pp.parse_mcp_panel(PANEL)[3]
        assert s.name == "basic-memory"
        assert s.tool_count == 42

    def test_needs_auth(self):
        s = pp.parse_mcp_panel(PANEL)[4]
        assert s.name == "claude.ai Figma"
        assert s.state == pp.NEEDS_AUTH

    def test_strips_selection_marker(self):
        s = pp.parse_mcp_panel(PANEL)[5]
        assert s.name == "tavily"

    def test_strips_checkbox_marker(self):
        s = pp.parse_mcp_panel(PANEL)[6]
        assert s.name == "exa"

    def test_chrome_lines_skipped(self):
        names = [s.name for s in pp.parse_mcp_panel(PANEL)]
        assert "74 servers" not in names
        assert not any("navigate" in n for n in names)


class TestParseLineEdges:
    def test_empty_line_none(self):
        assert pp.parse_line("") is None

    def test_whitespace_line_none(self):
        assert pp.parse_line("    ") is None

    def test_servers_header_none(self):
        assert pp.parse_line("128 servers") is None

    def test_bare_word_without_state_none(self):
        assert pp.parse_line("someword") is None

    def test_invalid_name_none(self):
        # leading punctuation that isn't a known marker → fails name regex
        assert pp.parse_line("!!! · ✔ connected") is None

    def test_leading_glyph_in_name_field(self):
        s = pp.parse_line("✔ context7 · connected · 5 tools")
        assert s is not None
        assert s.name == "context7"
        assert s.state == pp.CONNECTED
        assert s.tool_count == 5

    def test_keyword_state_without_glyph(self):
        s = pp.parse_line("myserver · disabled")
        assert s is not None
        assert s.state == pp.DISABLED

    def test_unknown_state_multi_field_still_returned(self):
        s = pp.parse_line("myserver · 12 tools")
        assert s is not None
        assert s.state == pp.UNKNOWN
        assert s.tool_count == 12

    def test_pipe_separator(self):
        s = pp.parse_line("gitlab | connected | 9 tools")
        assert s is not None
        assert s.name == "gitlab"
        assert s.tool_count == 9

    def test_error_keyword_maps_failed(self):
        s = pp.parse_line("brokensrv · error")
        assert s is not None
        assert s.state == pp.FAILED

    def test_only_separators_none(self):
        assert pp.parse_line("|||") is None

    def test_dedup_keeps_first(self):
        text = "tavily · ✔ connected\ntavily · ✘ failed"
        servers = pp.parse_mcp_panel(text)
        assert len(servers) == 1
        assert servers[0].state == pp.CONNECTED


class TestHelpers:
    def test_inventory_ids(self):
        servers = pp.parse_mcp_panel(PANEL)
        ids = pp.inventory_ids(servers)
        assert "apktool-mcp" in ids
        assert len(ids) == len(servers)

    def test_disabled_ids(self):
        servers = pp.parse_mcp_panel(PANEL)
        assert pp.disabled_ids(servers) == ["hexstrike-ai"]

    def test_enabled_property_true_for_connected(self):
        s = pp.ParsedServer(name="x", state=pp.CONNECTED)
        assert s.enabled is True
