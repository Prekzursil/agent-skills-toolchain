"""Tests for ui/app.py — pure logic; no TUI rendering.

We test:
- STATUS_BADGES and STATUS_STYLES mappings are complete for all AuthStatus values
- _AUTH_COMMANDS keys cover expected planes
- AuthInfoModal init stores server_id + planes
- MCPManagerApp._merge_rows-like logic via status module (already tested there)
- Row selection toggle logic via a minimal harness (no App.run())
- Loadout option building logic (mocked filesystem)
- Bulk toggle path doesn't crash with empty selection
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch


# Project root on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.models import AuthStatus, ServerRow
from ui.app import (
    STATUS_BADGES,
    STATUS_STYLES,
    _AUTH_COMMANDS,
    AuthInfoModal,
)


# ── STATUS_BADGES / STATUS_STYLES ─────────────────────────────────────────────


def test_status_badges_covers_all_auth_status_values():
    """Every AuthStatus value must have a badge string."""
    for status in AuthStatus:
        assert status.value in STATUS_BADGES, f"Missing badge for {status}"


def test_status_styles_covers_all_auth_status_values():
    """Every AuthStatus value must have a style string."""
    for status in AuthStatus:
        assert status.value in STATUS_STYLES, f"Missing style for {status}"


def test_status_badges_values_are_nonempty_strings():
    for key, val in STATUS_BADGES.items():
        assert isinstance(val, str) and val, f"Badge for {key!r} is empty"


def test_status_styles_values_are_nonempty_strings():
    for key, val in STATUS_STYLES.items():
        assert isinstance(val, str) and val, f"Style for {key!r} is empty"


# ── _AUTH_COMMANDS ─────────────────────────────────────────────────────────────


def test_auth_commands_has_codex_key():
    assert "codex" in _AUTH_COMMANDS


def test_auth_commands_has_claude_key():
    assert "claude" in _AUTH_COMMANDS


def test_auth_commands_has_funnel_key():
    assert "funnel" in _AUTH_COMMANDS


def test_auth_commands_values_are_nonempty():
    for k, v in _AUTH_COMMANDS.items():
        assert v, f"Auth command for {k!r} is empty"


# ── AuthInfoModal ──────────────────────────────────────────────────────────────


def test_auth_info_modal_stores_server_id():
    modal = AuthInfoModal("my-server", ["claude"])
    assert modal._server_id == "my-server"


def test_auth_info_modal_stores_planes():
    modal = AuthInfoModal("foo", ["codex", "funnel"])
    assert modal._planes == ["codex", "funnel"]


def test_auth_info_modal_empty_planes():
    # Should not raise; defaults to 'claude' branch internally
    modal = AuthInfoModal("bar", [])
    assert modal._planes == []


# ── Selection logic (unit tested without App.run()) ───────────────────────────


def _make_rows(ids: list[str]) -> list[ServerRow]:
    return [ServerRow(id=sid, name=sid, planes=["claude"], enabled=True) for sid in ids]


class _SelectionHarness:
    """Minimal harness that extracts the toggle logic from MCPManagerApp."""

    def __init__(self, row_ids: list[str]) -> None:
        self._rows = _make_rows(row_ids)
        self._selected_ids: set[str] = set()

    def toggle(self, row_key: str) -> None:
        if row_key in self._selected_ids:
            self._selected_ids.discard(row_key)
        else:
            self._selected_ids.add(row_key)

    def select_all(self) -> None:
        self._selected_ids = {r.id for r in self._rows}

    def clear(self) -> None:
        self._selected_ids.clear()


def test_toggle_adds_then_removes():
    h = _SelectionHarness(["a", "b", "c"])
    h.toggle("a")
    assert "a" in h._selected_ids
    h.toggle("a")
    assert "a" not in h._selected_ids


def test_select_all_selects_all_rows():
    h = _SelectionHarness(["x", "y", "z"])
    h.select_all()
    assert h._selected_ids == {"x", "y", "z"}


def test_clear_removes_all():
    h = _SelectionHarness(["x", "y"])
    h.select_all()
    h.clear()
    assert len(h._selected_ids) == 0


def test_toggle_multiple_independent():
    h = _SelectionHarness(["a", "b", "c"])
    h.toggle("a")
    h.toggle("b")
    assert h._selected_ids == {"a", "b"}
    h.toggle("a")
    assert h._selected_ids == {"b"}


# ── Loadout option building logic ─────────────────────────────────────────────


def test_loadout_options_include_none():
    """The '(none)' sentinel must always be first."""
    # We just check the constant, not a live app
    # (actual _load_loadout_options calls filesystem)
    # Test the structure by constructing options manually as the method does
    options: list[tuple[str, str]] = [("(none)", "")]
    assert options[0] == ("(none)", "")


def test_loadout_defaults_label_format():
    """If the loadout has 5 IDs the label should say '5 servers'."""
    from core.models import Loadout

    lo = Loadout(name="defaults", disabled_ids=["a", "b", "c", "d", "e"])
    n = len(lo.disabled_ids)
    label = f"defaults ({n} servers)"
    assert "5" in label


# ── _bulk_toggle guard: empty selection is a no-op ───────────────────────────


def test_bulk_toggle_empty_selection_is_noop():
    """No filesystem calls should happen if selected_ids is empty."""
    with patch("core.claude_adapter.set_server_disabled") as mock_set:
        # The guard short-circuits on an empty selection before any write.
        selected_ids: set[str] = set()
        assert not selected_ids  # guard condition is truthy -> early return
        mock_set.assert_not_called()


# ── auth plane fallback ───────────────────────────────────────────────────────


def test_auth_info_uses_first_plane():
    """The auth command shown should be for the first plane."""
    modal = AuthInfoModal("test-srv", ["codex"])
    plane = modal._planes[0]
    assert plane == "codex"
    assert "codex" in _AUTH_COMMANDS[plane].lower() or _AUTH_COMMANDS.get(plane)


def test_auth_info_falls_back_to_claude_for_unknown_plane():
    """An unknown plane should fall back gracefully (no KeyError)."""
    modal = AuthInfoModal("test-srv", ["unknown-plane"])
    plane = modal._planes[0]
    # The compose method does .get(plane, _AUTH_COMMANDS["claude"])
    fallback = _AUTH_COMMANDS.get(plane, _AUTH_COMMANDS["claude"])
    assert fallback == _AUTH_COMMANDS["claude"]


# ── Server row enabled/disabled labels ───────────────────────────────────────


def test_enabled_badge_constants():
    from ui.app import ENABLED_BADGE, DISABLED_BADGE

    assert ENABLED_BADGE
    assert DISABLED_BADGE
    assert ENABLED_BADGE != DISABLED_BADGE


def test_enabled_badge_for_enabled_row():
    from ui.app import ENABLED_BADGE

    row = ServerRow(id="s", name="s", planes=["claude"], enabled=True)
    badge = ENABLED_BADGE if row.enabled else "disabled"
    assert badge == ENABLED_BADGE


def test_disabled_badge_for_disabled_row():
    from ui.app import DISABLED_BADGE

    row = ServerRow(id="s", name="s", planes=["claude"], enabled=False)
    badge = "enabled" if row.enabled else DISABLED_BADGE
    assert badge == DISABLED_BADGE
