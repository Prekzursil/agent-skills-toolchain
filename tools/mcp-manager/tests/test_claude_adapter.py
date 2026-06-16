"""Tests for core/claude_adapter.py — parse, toggle, safe-write."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import claude_adapter  # noqa: E402
from core.models import AuthStatus  # noqa: E402

# ── Fixtures / helpers ─────────────────────────────────────────────────────────

MCP_LIST_SAMPLE = """\
Checking MCP server health…

claude.ai Tavily: https://mcp.tavily.com/mcp - ✔ Connected
claude.ai ChEMBL: https://hcls.mcp.claude.com/chembl/mcp - ✔ Connected
claude.ai Owkin: https://mcp.k.owkin.com/mcp - ! Needs authentication
claude.ai Google Drive: https://drivemcp.googleapis.com/mcp/v1 - ! Needs authentication
claude.ai Firebase: https://firebase.google.com - ✘ Failed to connect
plugin:chrome-devtools-mcp:chrome-devtools: npx chrome-devtools-mcp@1.2.0 - ✔ Connected
plugin:huggingface-skills:huggingface-skills: https://huggingface.co/mcp?login (HTTP) - ! Needs authentication
plugin:semgrep:semgrep: semgrep mcp - ✔ Connected
plugin:local-mcp-bridge:binary-ninja-mcp: npx -y binary-ninja-mcp --host localhost --port 9009 - ✔ Connected
plugin:local-mcp-bridge:github_cli: gh-cli-mcp  - ✔ Connected
"""


def _make_claude_json(tmp_path: Path, proj: str, disabled: list[str]) -> Path:
    cj = tmp_path / ".claude.json"
    cj.write_text(json.dumps({
        "numStartups": 42,
        "mcpServers": {"global-svc": {}},
        "projects": {proj: {"disabledMcpServers": list(disabled), "extra": True}},
    }), encoding="utf-8")
    return cj


# ── parse_mcp_list ─────────────────────────────────────────────────────────────


class TestParseMcpList:
    def test_header_line_skipped(self):
        rows = claude_adapter.parse_mcp_list(MCP_LIST_SAMPLE)
        ids = {r.id for r in rows}
        assert "Checking MCP server health…" not in ids

    def test_empty_lines_skipped(self):
        rows = claude_adapter.parse_mcp_list("\n\n  \n")
        assert rows == []

    def test_connected_status(self):
        rows = claude_adapter.parse_mcp_list(MCP_LIST_SAMPLE)
        by_id = {r.id: r for r in rows}
        assert by_id["claude.ai Tavily"].status == AuthStatus.CONNECTED

    def test_needs_auth_status(self):
        rows = claude_adapter.parse_mcp_list(MCP_LIST_SAMPLE)
        by_id = {r.id: r for r in rows}
        assert by_id["claude.ai Owkin"].status == AuthStatus.NEEDS_AUTH

    def test_failed_status(self):
        rows = claude_adapter.parse_mcp_list(MCP_LIST_SAMPLE)
        by_id = {r.id: r for r in rows}
        assert by_id["claude.ai Firebase"].status == AuthStatus.FAILED

    def test_plugin_namespaced_id_preserved(self):
        rows = claude_adapter.parse_mcp_list(MCP_LIST_SAMPLE)
        ids = {r.id for r in rows}
        assert "plugin:semgrep:semgrep" in ids
        assert "plugin:local-mcp-bridge:binary-ninja-mcp" in ids

    def test_plugin_short_name_derived(self):
        rows = claude_adapter.parse_mcp_list(MCP_LIST_SAMPLE)
        by_id = {r.id: r for r in rows}
        assert by_id["plugin:semgrep:semgrep"].name == "semgrep"
        assert by_id["plugin:chrome-devtools-mcp:chrome-devtools"].name == "chrome-devtools"

    def test_claude_ai_short_name_derived(self):
        rows = claude_adapter.parse_mcp_list(MCP_LIST_SAMPLE)
        by_id = {r.id: r for r in rows}
        assert by_id["claude.ai Tavily"].name == "Tavily"

    def test_plane_is_claude(self):
        rows = claude_adapter.parse_mcp_list(MCP_LIST_SAMPLE)
        for r in rows:
            assert r.planes == ["claude"]

    def test_all_enabled_before_reconcile(self):
        rows = claude_adapter.parse_mcp_list(MCP_LIST_SAMPLE)
        assert all(r.enabled for r in rows)

    def test_no_duplicates(self):
        # Feeding the same output twice should not produce duplicate rows
        doubled = MCP_LIST_SAMPLE + "\n" + MCP_LIST_SAMPLE
        rows = claude_adapter.parse_mcp_list(doubled)
        ids = [r.id for r in rows]
        assert len(ids) == len(set(ids))

    def test_all_ten_servers_parsed(self):
        rows = claude_adapter.parse_mcp_list(MCP_LIST_SAMPLE)
        assert len(rows) == 10


# ── reconcile_enabled ──────────────────────────────────────────────────────────


class TestReconcileEnabled:
    def test_disabled_id_sets_enabled_false(self):
        rows = claude_adapter.parse_mcp_list(MCP_LIST_SAMPLE)
        claude_adapter.reconcile_enabled(rows, {"plugin:semgrep:semgrep"})
        by_id = {r.id: r for r in rows}
        assert by_id["plugin:semgrep:semgrep"].enabled is False
        assert by_id["claude.ai Tavily"].enabled is True

    def test_empty_disabled_leaves_all_enabled(self):
        rows = claude_adapter.parse_mcp_list(MCP_LIST_SAMPLE)
        claude_adapter.reconcile_enabled(rows, set())
        assert all(r.enabled for r in rows)


# ── get_disabled_ids ───────────────────────────────────────────────────────────


class TestGetDisabledIds:
    def test_reads_from_project_block(self, tmp_path: Path):
        proj = "C:/my/project"
        cj = _make_claude_json(tmp_path, proj, ["plugin:a:b", "claude.ai Foo"])
        ids = claude_adapter.get_disabled_ids(cj, proj)
        assert ids == {"plugin:a:b", "claude.ai Foo"}

    def test_missing_file_returns_empty_set(self, tmp_path: Path):
        ids = claude_adapter.get_disabled_ids(tmp_path / "nonexistent.json", "C:/x")
        assert ids == set()

    def test_missing_project_returns_empty_set(self, tmp_path: Path):
        cj = _make_claude_json(tmp_path, "C:/other", ["id1"])
        ids = claude_adapter.get_disabled_ids(cj, "C:/nowhere")
        assert ids == set()


# ── get_server_universe ────────────────────────────────────────────────────────


class TestGetServerUniverse:
    def test_disabled_servers_reflected(self, tmp_path: Path):
        proj = "C:/proj"
        cj = _make_claude_json(tmp_path, proj, ["plugin:semgrep:semgrep"])
        rows = claude_adapter.get_server_universe(
            cj, proj, mcp_list_output=MCP_LIST_SAMPLE
        )
        by_id = {r.id: r for r in rows}
        assert by_id["plugin:semgrep:semgrep"].enabled is False
        assert by_id["claude.ai Tavily"].enabled is True

    def test_no_disabled_all_enabled(self, tmp_path: Path):
        proj = "C:/proj"
        cj = _make_claude_json(tmp_path, proj, [])
        rows = claude_adapter.get_server_universe(
            cj, proj, mcp_list_output=MCP_LIST_SAMPLE
        )
        assert all(r.enabled for r in rows)


# ── set_server_disabled ────────────────────────────────────────────────────────


class TestSetServerDisabled:
    def test_disable_adds_to_array(self, tmp_path: Path):
        proj = "C:/p"
        cj = _make_claude_json(tmp_path, proj, [])
        changed = claude_adapter.set_server_disabled(cj, proj, "claude.ai PubMed", True)
        assert changed is True
        data = json.loads(cj.read_text(encoding="utf-8"))
        assert "claude.ai PubMed" in data["projects"][proj]["disabledMcpServers"]

    def test_enable_removes_from_array(self, tmp_path: Path):
        proj = "C:/p"
        cj = _make_claude_json(tmp_path, proj, ["claude.ai PubMed"])
        changed = claude_adapter.set_server_disabled(cj, proj, "claude.ai PubMed", False)
        assert changed is True
        data = json.loads(cj.read_text(encoding="utf-8"))
        assert "claude.ai PubMed" not in data["projects"][proj]["disabledMcpServers"]

    def test_idempotent_disable(self, tmp_path: Path):
        proj = "C:/p"
        cj = _make_claude_json(tmp_path, proj, ["plugin:a:b"])
        assert claude_adapter.set_server_disabled(cj, proj, "plugin:a:b", True) is False

    def test_idempotent_enable(self, tmp_path: Path):
        proj = "C:/p"
        cj = _make_claude_json(tmp_path, proj, [])
        assert claude_adapter.set_server_disabled(cj, proj, "plugin:a:b", False) is False

    def test_other_keys_preserved(self, tmp_path: Path):
        proj = "C:/p"
        cj = _make_claude_json(tmp_path, proj, [])
        claude_adapter.set_server_disabled(cj, proj, "plugin:x:y", True)
        data = json.loads(cj.read_text(encoding="utf-8"))
        assert data["numStartups"] == 42
        assert data["projects"][proj]["extra"] is True

    def test_backup_created(self, tmp_path: Path):
        proj = "C:/p"
        cj = _make_claude_json(tmp_path, proj, [])
        claude_adapter.set_server_disabled(cj, proj, "plugin:x:y", True)
        bak_dir = cj.parent / ".mcp-manager-backups"
        baks = list(bak_dir.glob("claude.json.*.bak"))
        assert len(baks) >= 1

    def test_new_project_block_created(self, tmp_path: Path):
        cj = tmp_path / ".claude.json"
        cj.write_text(json.dumps({"mcpServers": {}}), encoding="utf-8")
        claude_adapter.set_server_disabled(cj, "C:/new/proj", "svc", True)
        data = json.loads(cj.read_text(encoding="utf-8"))
        assert data["projects"]["C:/new/proj"]["disabledMcpServers"] == ["svc"]

    def test_exact_namespaced_id_no_partial_match(self, tmp_path: Path):
        proj = "C:/p"
        cj = _make_claude_json(tmp_path, proj, ["plugin:a:full"])
        # adding a different id must not affect the existing one
        claude_adapter.set_server_disabled(cj, proj, "plugin:a:full-2", True)
        data = json.loads(cj.read_text(encoding="utf-8"))
        arr = data["projects"][proj]["disabledMcpServers"]
        assert "plugin:a:full" in arr
        assert "plugin:a:full-2" in arr
