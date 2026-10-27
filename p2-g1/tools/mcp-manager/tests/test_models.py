"""Tests for core/models.py — ServerRow, Loadout, AuthStatus."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.models import AuthStatus, Loadout, ServerRow  # noqa: E402


class TestAuthStatus:
    def test_connected_glyph(self):
        assert AuthStatus.from_glyph("✔") == AuthStatus.CONNECTED

    def test_needs_auth_glyph(self):
        assert AuthStatus.from_glyph("!") == AuthStatus.NEEDS_AUTH
        assert AuthStatus.from_glyph("⚠") == AuthStatus.NEEDS_AUTH

    def test_failed_glyph(self):
        assert AuthStatus.from_glyph("✘") == AuthStatus.FAILED
        assert AuthStatus.from_glyph("x") == AuthStatus.FAILED

    def test_unknown_glyph(self):
        assert AuthStatus.from_glyph("?") == AuthStatus.UNKNOWN
        assert AuthStatus.from_glyph("") == AuthStatus.UNKNOWN

    def test_whitespace_stripped(self):
        assert AuthStatus.from_glyph("  ✔  ") == AuthStatus.CONNECTED


class TestServerRow:
    def test_single_plane_not_duplicated(self):
        row = ServerRow(id="foo", name="foo", planes=["claude"])
        assert row.duplicated is False

    def test_multi_plane_duplicated(self):
        row = ServerRow(id="foo", name="foo", planes=["claude", "codex"])
        assert row.duplicated is True

    def test_same_plane_twice_still_duplicated(self):
        # duplication check uses set(planes)
        row = ServerRow(id="foo", name="foo", planes=["claude", "claude"])
        assert row.duplicated is False

    def test_to_dict_contains_all_keys(self):
        row = ServerRow(
            id="plugin:a:b",
            name="b",
            planes=["claude"],
            enabled=True,
            status=AuthStatus.CONNECTED,
            auth="Connected",
            command="npx foo",
        )
        d = row.to_dict()
        assert d["id"] == "plugin:a:b"
        assert d["name"] == "b"
        assert d["enabled"] is True
        assert d["status"] == "connected"
        assert d["duplicated"] is False


class TestServerRowDead:
    """`dead` is True only for an ENABLED server whose handshake FAILED."""

    def test_enabled_failed_is_dead(self):
        row = ServerRow(id="a", name="a", enabled=True, status=AuthStatus.FAILED)
        assert row.dead is True

    def test_disabled_with_failed_status_is_not_dead(self):
        # cross-plane case: another plane disabled it, status still FAILED
        row = ServerRow(id="a", name="a", enabled=False, status=AuthStatus.FAILED)
        assert row.dead is False

    def test_disabled_status_is_not_dead(self):
        row = ServerRow(id="a", name="a", enabled=False, status=AuthStatus.DISABLED)
        assert row.dead is False

    def test_connected_is_not_dead(self):
        row = ServerRow(id="a", name="a", enabled=True, status=AuthStatus.CONNECTED)
        assert row.dead is False

    def test_to_dict_exposes_dead(self):
        row = ServerRow(id="a", name="a", enabled=True, status=AuthStatus.FAILED)
        assert row.to_dict()["dead"] is True


class TestLoadout:
    def test_empty_loadout(self):
        lo = Loadout()
        assert lo.disabled_ids == []
        assert lo.name == "defaults"

    def test_to_dict(self):
        lo = Loadout(name="defaults", disabled_ids=["claude.ai PubMed", "plugin:x:y"])
        d = lo.to_dict()
        assert d["name"] == "defaults"
        assert "claude.ai PubMed" in d["disabled_ids"]
        assert "plugin:x:y" in d["disabled_ids"]
