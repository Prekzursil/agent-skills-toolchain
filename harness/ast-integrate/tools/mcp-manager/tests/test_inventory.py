"""Tests for the cross-plane MCP + skill inventory (read-only core)."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import inventory  # noqa: E402


@pytest.fixture
def home(tmp_path: Path) -> Path:
    """A fake $HOME with all four planes populated + duplicate skill packs."""
    # ~/.claude.json : user scope (github enabled, semgrep disabled) + a project block
    proj = str(tmp_path).replace("\\", "/")
    (tmp_path / ".claude.json").write_text(
        json.dumps(
            {
                "mcpServers": {"github": {}, "semgrep": {}},
                "disabledMcpServers": ["semgrep"],
                "projects": {
                    proj: {
                        "mcpServers": {"ida-pro-mcp": {}},
                        "disabledMcpServers": [],
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    # ~/.mcp.json : project scope (context7 enabled, browserstack disabled)
    (tmp_path / ".mcp.json").write_text(
        json.dumps(
            {
                "mcpServers": {"context7": {}, "browserstack": {"disabled": True}},
            }
        ),
        encoding="utf-8",
    )
    # ~/.codex/config.toml
    (tmp_path / ".codex").mkdir()
    (tmp_path / ".codex" / "config.toml").write_text(
        '[mcp_servers.github]\ncommand = "gh-cli-mcp"\nenabled = true\n'
        '[mcp_servers.exa]\ncommand = "exa"\nenabled = false\n',
        encoding="utf-8",
    )
    # ~/.mcp-funnel-master.json
    (tmp_path / ".mcp-funnel-master.json").write_text(
        json.dumps(
            {
                "servers": [{"name": "ghidra-mcp"}, {"name": "github"}],
            }
        ),
        encoding="utf-8",
    )
    # duplicate skill packs: packA and packB expose the SAME skill names; packC differs
    skills = tmp_path / ".claude" / "skills"
    for pack, names in {
        "packA": ["docx", "pdf"],
        "packB": ["docx", "pdf"],
        "packC": ["unique"],
    }.items():
        for n in names:
            d = skills / pack / n
            d.mkdir(parents=True)
            (d / "SKILL.md").write_text(f"---\nname: {n}\n---\n", encoding="utf-8")
    return tmp_path


def test_scan_claude_user_enabled_and_disabled(home: Path):
    inv = inventory.scan_claude(
        home / ".claude.json", project_path=str(home).replace("\\", "/")
    )
    assert inv["github"].enabled_in == ["claude-user"]
    assert inv["semgrep"].disabled_in == ["claude-user"]
    assert "claude-project" in inv["ida-pro-mcp"].enabled_in


def test_scan_mcp_json_disabled_flag(home: Path):
    inv = inventory.scan_mcp_json(home / ".mcp.json")
    assert inv["context7"].enabled_in == ["mcp.json"]
    assert inv["browserstack"].disabled_in == ["mcp.json"]


def test_scan_codex_enabled_flag(home: Path):
    inv = inventory.scan_codex(home / ".codex" / "config.toml")
    assert inv["github"].enabled_in == ["codex"]
    assert inv["exa"].disabled_in == ["codex"]


def test_scan_funnel_servers(home: Path):
    inv = inventory.scan_funnel(home / ".mcp-funnel-master.json")
    assert set(inv) == {"ghidra-mcp", "github"}
    assert inv["github"].enabled_in == ["funnel"]


def test_merge_detects_cross_plane_duplicate(home: Path):
    rep = inventory.build_inventory(home, project_path=str(home).replace("\\", "/"))
    # github appears in claude-user + codex + funnel -> duplicated across planes
    assert "github" in rep["duplicated_servers"]
    gh = next(s for s in rep["servers"] if s["name"] == "github")
    assert gh["duplicated"] is True
    assert set(gh["planes"]) >= {"claude-user", "codex", "funnel"}


def test_duplicate_skill_pack_detection(home: Path):
    rep = inventory.build_inventory(home, project_path=str(home).replace("\\", "/"))
    groups = rep["duplicate_skill_packs"]
    assert len(groups) == 1
    assert len(groups[0]) == 2  # packA + packB (identical name sets), packC excluded


def test_missing_files_are_safe(tmp_path: Path):
    # no config files at all -> empty, no exceptions
    rep = inventory.build_inventory(tmp_path, project_path=None)
    assert rep["server_count"] == 0
    assert rep["duplicate_skill_packs"] == []
