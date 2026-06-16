"""Tests for core/funnel_adapter.py — profile reads, server universe, switch."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import funnel_adapter  # noqa: E402
from core.models import AuthStatus  # noqa: E402

# ── Fixtures ──────────────────────────────────────────────────────────────────

PROFILES = {
    "_comment": "Named MCP profiles",
    "profiles": {
        "default": "*ALL*",
        "minimal": ["github_cli", "repomix", "semgrep"],
        "re": ["binary-ninja-mcp", "ghidra-mcp", "ida-pro-mcp", "frida-mcp", "github_cli"],
        "web": ["chrome-devtools", "firecrawl", "tavily", "github_cli"],
    }
}


def _make_profiles(tmp_path: Path) -> Path:
    pf = tmp_path / ".mcp-funnel-profiles.json"
    pf.write_text(json.dumps(PROFILES), encoding="utf-8")
    return pf


# ── load_profiles ─────────────────────────────────────────────────────────────


class TestLoadProfiles:
    def test_returns_profiles_dict(self, tmp_path: Path):
        pf = _make_profiles(tmp_path)
        profiles = funnel_adapter.load_profiles(pf)
        assert "default" in profiles
        assert "re" in profiles

    def test_missing_file_returns_empty(self, tmp_path: Path):
        profiles = funnel_adapter.load_profiles(tmp_path / "nope.json")
        assert profiles == {}


# ── get_profile_servers ───────────────────────────────────────────────────────


class TestGetProfileServers:
    def test_default_returns_all_sentinel(self, tmp_path: Path):
        pf = _make_profiles(tmp_path)
        servers = funnel_adapter.get_profile_servers("default", pf)
        assert servers == ["*ALL*"]

    def test_named_profile_returns_list(self, tmp_path: Path):
        pf = _make_profiles(tmp_path)
        servers = funnel_adapter.get_profile_servers("minimal", pf)
        assert "github_cli" in servers
        assert "semgrep" in servers

    def test_missing_profile_returns_none(self, tmp_path: Path):
        pf = _make_profiles(tmp_path)
        assert funnel_adapter.get_profile_servers("nonexistent", pf) is None


# ── get_server_universe ────────────────────────────────────────────────────────


class TestGetServerUniverse:
    def test_returns_union_of_all_non_default_profiles(self, tmp_path: Path):
        pf = _make_profiles(tmp_path)
        rows = funnel_adapter.get_server_universe(pf)
        ids = {r.id for r in rows}
        # union of minimal + re + web (default=*ALL* skipped)
        assert "github_cli" in ids
        assert "binary-ninja-mcp" in ids
        assert "chrome-devtools" in ids
        assert "ida-pro-mcp" in ids
        assert "*ALL*" not in ids

    def test_no_duplicates(self, tmp_path: Path):
        pf = _make_profiles(tmp_path)
        rows = funnel_adapter.get_server_universe(pf)
        ids = [r.id for r in rows]
        assert len(ids) == len(set(ids))

    def test_plane_is_funnel(self, tmp_path: Path):
        pf = _make_profiles(tmp_path)
        rows = funnel_adapter.get_server_universe(pf)
        for r in rows:
            assert r.planes == ["funnel"]

    def test_all_enabled_by_default(self, tmp_path: Path):
        pf = _make_profiles(tmp_path)
        rows = funnel_adapter.get_server_universe(pf)
        assert all(r.enabled for r in rows)

    def test_sorted_by_id(self, tmp_path: Path):
        pf = _make_profiles(tmp_path)
        rows = funnel_adapter.get_server_universe(pf)
        ids = [r.id for r in rows]
        assert ids == sorted(ids)

    def test_missing_file_returns_empty(self, tmp_path: Path):
        rows = funnel_adapter.get_server_universe(tmp_path / "nope.json")
        assert rows == []


# ── list_profiles ─────────────────────────────────────────────────────────────


class TestListProfiles:
    def test_returns_sorted_profile_names(self, tmp_path: Path):
        pf = _make_profiles(tmp_path)
        names = funnel_adapter.list_profiles(pf)
        assert names == sorted(names)
        assert "default" in names
        assert "re" in names

    def test_missing_file_returns_empty(self, tmp_path: Path):
        assert funnel_adapter.list_profiles(tmp_path / "nope.json") == []


# ── switch_profile ────────────────────────────────────────────────────────────


class TestSwitchProfile:
    def test_unknown_profile_returns_false(self, tmp_path: Path):
        pf = _make_profiles(tmp_path)
        script = tmp_path / "mcp-profile.ps1"
        script.write_text("", encoding="utf-8")
        ok, msg = funnel_adapter.switch_profile(
            "nonexistent", script_path=script, profiles_json=pf
        )
        assert ok is False
        assert "nonexistent" in msg

    def test_dry_run_does_not_execute(self, tmp_path: Path):
        pf = _make_profiles(tmp_path)
        script = tmp_path / "mcp-profile.ps1"
        # script doesn't need to exist for dry_run
        ok, msg = funnel_adapter.switch_profile(
            "minimal", script_path=script, profiles_json=pf, dry_run=True
        )
        assert ok is True
        assert "dry-run" in msg

    def test_dry_run_includes_profile_name(self, tmp_path: Path):
        pf = _make_profiles(tmp_path)
        script = tmp_path / "mcp-profile.ps1"
        ok, msg = funnel_adapter.switch_profile(
            "re", script_path=script, profiles_json=pf, dry_run=True
        )
        assert "re" in msg

    def test_available_profiles_listed_on_error(self, tmp_path: Path):
        pf = _make_profiles(tmp_path)
        script = tmp_path / "mcp-profile.ps1"
        _, msg = funnel_adapter.switch_profile(
            "nope", script_path=script, profiles_json=pf
        )
        # error message should list at least some known profiles
        assert any(name in msg for name in ["default", "minimal", "re", "web"])
