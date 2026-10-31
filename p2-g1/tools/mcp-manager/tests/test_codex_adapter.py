"""Tests for core/codex_adapter.py — parse, toggle, fallback."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import codex_adapter  # noqa: E402

# ── Fixtures ──────────────────────────────────────────────────────────────────

CODEX_JSON_SAMPLE = json.dumps(
    [
        {"name": "exa", "enabled": True, "auth_status": "bearer_token"},
        {"name": "context7", "enabled": True, "auth_status": "unsupported"},
        {"name": "kaggle", "enabled": False, "auth_status": None},
        {"name": "figma", "enabled": True, "auth_status": "unsupported"},
    ]
)

CODEX_TOML_SAMPLE = (
    "# my codex config\n"
    "[mcp_servers.exa]\n"
    'url = "https://mcp.exa.ai/mcp"\n'
    "enabled = true\n"
    "\n"
    "[mcp_servers.kaggle]\n"
    'command = "python"\n'
    "enabled = false\n"
    "\n"
    "[mcp_servers.figma]\n"
    'command = "npx figma"\n'
    "# no explicit enabled = defaults to true\n"
)


# ── parse_codex_mcp_list ──────────────────────────────────────────────────────


class TestParseCodexMcpList:
    def test_parses_enabled_servers(self):
        rows = codex_adapter.parse_codex_mcp_list(CODEX_JSON_SAMPLE)
        by_id = {r.id: r for r in rows}
        assert by_id["exa"].enabled is True
        assert by_id["context7"].enabled is True

    def test_parses_disabled_server(self):
        rows = codex_adapter.parse_codex_mcp_list(CODEX_JSON_SAMPLE)
        by_id = {r.id: r for r in rows}
        assert by_id["kaggle"].enabled is False

    def test_plane_is_codex(self):
        rows = codex_adapter.parse_codex_mcp_list(CODEX_JSON_SAMPLE)
        for r in rows:
            assert r.planes == ["codex"]

    def test_invalid_json_returns_empty(self):
        assert codex_adapter.parse_codex_mcp_list("not json") == []

    def test_non_list_returns_empty(self):
        assert codex_adapter.parse_codex_mcp_list('{"foo": 1}') == []

    def test_missing_name_skipped(self):
        bad = json.dumps([{"enabled": True}, {"name": "ok", "enabled": True}])
        rows = codex_adapter.parse_codex_mcp_list(bad)
        assert len(rows) == 1
        assert rows[0].id == "ok"

    def test_all_four_servers_parsed(self):
        rows = codex_adapter.parse_codex_mcp_list(CODEX_JSON_SAMPLE)
        assert len(rows) == 4


# ── get_server_universe ────────────────────────────────────────────────────────


class TestGetServerUniverse:
    def test_uses_injected_json_output(self, tmp_path: Path):
        ct = tmp_path / "config.toml"
        ct.write_text(CODEX_TOML_SAMPLE, encoding="utf-8")
        rows = codex_adapter.get_server_universe(ct, json_output=CODEX_JSON_SAMPLE)
        assert len(rows) == 4

    def test_falls_back_to_toml_when_json_empty(self, tmp_path: Path):
        ct = tmp_path / "config.toml"
        ct.write_text(CODEX_TOML_SAMPLE, encoding="utf-8")
        rows = codex_adapter.get_server_universe(ct, json_output="[]")
        # empty JSON list => falls back to TOML (3 servers in sample)
        assert len(rows) == 3

    def test_toml_fallback_respects_enabled_flag(self, tmp_path: Path):
        ct = tmp_path / "config.toml"
        ct.write_text(CODEX_TOML_SAMPLE, encoding="utf-8")
        rows = codex_adapter.get_server_universe(ct, json_output="[]")
        by_id = {r.id: r for r in rows}
        assert by_id["exa"].enabled is True
        assert by_id["kaggle"].enabled is False

    def test_missing_toml_returns_empty(self, tmp_path: Path):
        rows = codex_adapter.get_server_universe(
            tmp_path / "nope.toml", json_output="[]"
        )
        assert rows == []


# ── set_server_enabled ─────────────────────────────────────────────────────────


class TestSetServerEnabled:
    def test_disable_writes_false(self, tmp_path: Path):
        pytest.importorskip("tomlkit")
        ct = tmp_path / "config.toml"
        ct.write_text(CODEX_TOML_SAMPLE, encoding="utf-8")
        assert codex_adapter.set_server_enabled(ct, "exa", False) is True
        import tomllib

        data = tomllib.loads(ct.read_text(encoding="utf-8"))
        assert data["mcp_servers"]["exa"]["enabled"] is False

    def test_enable_writes_true(self, tmp_path: Path):
        pytest.importorskip("tomlkit")
        ct = tmp_path / "config.toml"
        ct.write_text(CODEX_TOML_SAMPLE, encoding="utf-8")
        assert codex_adapter.set_server_enabled(ct, "kaggle", True) is True
        import tomllib

        data = tomllib.loads(ct.read_text(encoding="utf-8"))
        assert data["mcp_servers"]["kaggle"]["enabled"] is True

    def test_idempotent_returns_false(self, tmp_path: Path):
        pytest.importorskip("tomlkit")
        ct = tmp_path / "config.toml"
        ct.write_text(CODEX_TOML_SAMPLE, encoding="utf-8")
        assert codex_adapter.set_server_enabled(ct, "exa", True) is False

    def test_comments_preserved(self, tmp_path: Path):
        pytest.importorskip("tomlkit")
        ct = tmp_path / "config.toml"
        ct.write_text(CODEX_TOML_SAMPLE, encoding="utf-8")
        codex_adapter.set_server_enabled(ct, "exa", False)
        text = ct.read_text(encoding="utf-8")
        assert "# my codex config" in text
        assert "# no explicit enabled" in text

    def test_missing_server_raises_key_error(self, tmp_path: Path):
        pytest.importorskip("tomlkit")
        ct = tmp_path / "config.toml"
        ct.write_text(CODEX_TOML_SAMPLE, encoding="utf-8")
        with pytest.raises(KeyError):
            codex_adapter.set_server_enabled(ct, "nonexistent", False)

    def test_backup_created(self, tmp_path: Path):
        pytest.importorskip("tomlkit")
        ct = tmp_path / "config.toml"
        ct.write_text(CODEX_TOML_SAMPLE, encoding="utf-8")
        codex_adapter.set_server_enabled(ct, "exa", False)
        bak_dir = ct.parent / ".mcp-manager-backups"
        baks = list(bak_dir.glob("config.toml.*.bak"))
        assert len(baks) >= 1

    def test_result_is_valid_toml(self, tmp_path: Path):
        pytest.importorskip("tomlkit")
        import tomllib

        ct = tmp_path / "config.toml"
        ct.write_text(CODEX_TOML_SAMPLE, encoding="utf-8")
        codex_adapter.set_server_enabled(ct, "kaggle", True)
        # should not raise
        tomllib.loads(ct.read_text(encoding="utf-8"))
