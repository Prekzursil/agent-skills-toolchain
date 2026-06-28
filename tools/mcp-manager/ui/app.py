"""mcp-manager TUI — Textual App for cross-plane MCP server management.

Columns: status | server | plane(s) | enabled | auth
Features:
  - Async Refresh with spinner (never blocks the UI; uses Textual workers)
  - Row multi-selection with checkboxes for bulk enable/disable
  - Loadout dropdown (apply a saved disable-list to a project)
  - Auth-launch button: opens the correct external auth flow and explains
    honestly that OAuth completion happens in the browser/terminal, not here.
  - Status badges: connected / error / disabled / needs-auth / pending

Run:
    uv run --with textual ui/app.py
    or (with deps installed):
    python ui/app.py
"""

from __future__ import annotations
from typing import ClassVar, cast, final
import sys
from pathlib import Path

from typing_extensions import override

# Ensure the project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Container, Horizontal, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Label,
    LoadingIndicator,
    Select,
    Static,
)

from core.models import AuthStatus, ServerRow
from core import loadout as loadout_mod
from core import funnel_adapter

# ── Constants ─────────────────────────────────────────────────────────────────

STATUS_BADGES: dict[str, str] = {
    AuthStatus.CONNECTED.value: "● connected",
    AuthStatus.NEEDS_AUTH.value: "⚠ needs-auth",
    AuthStatus.FAILED.value: "✘ error",
    AuthStatus.UNKNOWN.value: "? pending",
}
STATUS_STYLES: dict[str, str] = {
    AuthStatus.CONNECTED.value: "bold green",
    AuthStatus.NEEDS_AUTH.value: "bold yellow",
    AuthStatus.FAILED.value: "bold red",
    AuthStatus.UNKNOWN.value: "dim",
}
ENABLED_BADGE = "enabled"
DISABLED_BADGE = "disabled"

# Auth command templates by plane/hint — used in the auth dialog
_AUTH_COMMANDS: dict[str, str] = {
    "codex": "codex mcp login <server-name>",
    "claude": "Open Claude Code and run: /mcp, then select the server",
    "funnel": "Run: mcp-profile.ps1 <profile-name>  (switches the active funnel profile)",
}


# ── Messages ──────────────────────────────────────────────────────────────────


@final
class RefreshComplete(Message):
    """Sent when a background refresh finishes."""

    def __init__(self, rows: list[ServerRow]) -> None:
        super().__init__()
        self.rows = rows


@final
class RefreshFailed(Message):
    """Sent when a background refresh fails."""

    def __init__(self, error: str) -> None:
        super().__init__()
        self.error = error


# ── Widgets ───────────────────────────────────────────────────────────────────


@final
class StatusBar(Static):
    """One-line status bar at the bottom of the table panel."""

    DEFAULT_CSS = """
    StatusBar {
        height: 1;
        padding: 0 1;
        background: $panel;
        color: $text-muted;
    }
    """

    status_text: reactive[str] = reactive("Ready")

    @override
    def render(self) -> str:
        return self.status_text


class AuthInfoModal(Container):
    """Inline panel that explains how to authenticate a server.

    Displayed below the bulk-action bar; dismissed by pressing Esc or clicking
    the close button.  We cannot complete OAuth flows — we explain what command
    to run.
    """

    DEFAULT_CSS: ClassVar[str] = """
    AuthInfoModal {
        height: auto;
        border: solid $warning;
        padding: 1 2;
        margin: 1 0;
        background: $panel;
    }
    AuthInfoModal Label {
        width: 100%;
    }
    AuthInfoModal #auth-close {
        dock: right;
        margin-top: 0;
    }
    """

    def __init__(self, server_id: str, planes: list[str]) -> None:
        super().__init__()
        self._server_id: str = server_id
        self._planes: list[str] = planes

    @override
    def compose(self) -> ComposeResult:
        plane = self._planes[0] if self._planes else "claude"
        cmd = _AUTH_COMMANDS.get(plane, _AUTH_COMMANDS["claude"])
        yield Label(
            f"[bold yellow]Authenticate:[/] [bold]{self._server_id}[/]\n\n"
            + "mcp-manager cannot complete OAuth or store credentials — that must\n"
            + "happen in the host application. Run this in a terminal or the app:\n\n"
            + f"  [bold cyan]{cmd}[/]\n\n"
            + "After authentication the server status will update on next Refresh.",
            id="auth-label",
        )
        yield Button("Close", id="auth-close", variant="default")

    @on(Button.Pressed, "#auth-close")
    def _close(self) -> None:
        _ = self.remove()


# ── Main App ──────────────────────────────────────────────────────────────────


class MCPManagerApp(App[None]):
    """Cross-plane MCP server manager TUI."""

    TITLE: str | None = "mcp-manager"
    SUB_TITLE: str | None = "cross-plane MCP server manager"

    CSS: ClassVar[str] = """
    Screen {
        layout: vertical;
    }

    #main-container {
        height: 1fr;
        layout: vertical;
    }

    #toolbar {
        height: 3;
        layout: horizontal;
        background: $panel;
        border-bottom: solid $primary;
        padding: 0 1;
        align: left middle;
    }

    #toolbar Button {
        margin: 0 1 0 0;
        min-width: 12;
    }

    #toolbar Select {
        width: 28;
        margin: 0 1 0 0;
    }

    #toolbar Label {
        margin: 0 1 0 0;
        color: $text-muted;
    }

    #table-container {
        height: 1fr;
        overflow: auto;
    }

    #loading-overlay {
        height: 3;
        layout: horizontal;
        align: center middle;
        background: $panel;
        display: none;
    }

    #loading-overlay.visible {
        display: block;
    }

    #bulk-bar {
        height: 3;
        layout: horizontal;
        background: $panel;
        border-top: solid $primary;
        padding: 0 1;
        align: left middle;
    }

    #bulk-bar Button {
        margin: 0 1 0 0;
        min-width: 16;
    }

    #bulk-bar Label {
        margin: 0 1 0 0;
        color: $text-muted;
    }

    #auth-panel {
        height: auto;
        padding: 0 1;
    }

    #status-bar {
        height: 1;
        dock: bottom;
    }

    DataTable {
        height: 1fr;
    }
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("r", "refresh", "Refresh", show=True),
        Binding("e", "enable_selected", "Enable sel.", show=True),
        Binding("d", "disable_selected", "Disable sel.", show=True),
        Binding("a", "authenticate_selected", "Authenticate", show=True),
        Binding("space", "toggle_row", "Toggle select", show=True),
        Binding("ctrl+a", "select_all", "Select all", show=True),
        Binding("escape", "clear_selection", "Clear sel.", show=True),
        Binding("q", "quit", "Quit", show=True),
    ]

    # ── state ─────────────────────────────────────────────────────────────────

    _rows: list[ServerRow] = []
    _selected_ids: set[str] = set()
    _loading: reactive[bool] = reactive(False)
    _loadout_profiles: list[tuple[str, str]] = []

    # ── compose ───────────────────────────────────────────────────────────────

    @override
    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="main-container"):
            with Horizontal(id="toolbar"):
                yield Button("⟳ Refresh", id="btn-refresh", variant="primary")
                yield Label("Loadout:")
                yield Select(
                    options=[("(none)", "")],
                    id="loadout-select",
                    allow_blank=True,
                    prompt="Select loadout…",
                )
                yield Button("Apply Loadout", id="btn-apply-loadout", variant="default")

            with Container(id="loading-overlay"):
                yield LoadingIndicator(id="spinner")
                yield Label("Refreshing…", id="loading-label")

            with Container(id="table-container"):
                yield DataTable(
                    id="server-table", zebra_stripes=True, cursor_type="row"
                )

            with Horizontal(id="bulk-bar"):
                yield Label("Selection:", id="sel-label")
                yield Button("Enable selected", id="btn-enable", variant="success")
                yield Button("Disable selected", id="btn-disable", variant="error")
                yield Button("Authenticate…", id="btn-auth", variant="warning")

            with Container(id="auth-panel"):
                pass  # auth info widget injected here on demand

        yield StatusBar(id="status-bar")
        yield Footer()

    # ── on_mount ──────────────────────────────────────────────────────────────

    def on_mount(self) -> None:
        self._selected_ids = set()
        self._setup_table()
        self._load_loadout_options()
        self.action_refresh()

    def _setup_table(self) -> None:
        table = cast("DataTable[str]", self.query_one("#server-table", DataTable))
        _ = table.add_column("Sel", width=3)
        _ = table.add_column("Status", width=14)
        _ = table.add_column("Server", width=34)
        _ = table.add_column("Plane(s)", width=16)
        _ = table.add_column("Enabled", width=9)
        _ = table.add_column("Auth info", width=24)

    def _load_loadout_options(self) -> None:
        """Populate the loadout dropdown from ~/.claude/.mcp-disabled-defaults.json
        and funnel profiles."""
        options: list[tuple[str, str]] = [("(none)", "")]

        # Loadout: the single defaults file is always option "defaults"
        try:
            lo = loadout_mod.read_loadout()
            if lo.disabled_ids:
                n = len(lo.disabled_ids)
                options.append((f"defaults ({n} servers)", "__defaults__"))
        except Exception:  # noqa: BLE001
            pass

        # Funnel profiles
        try:
            profiles = funnel_adapter.list_profiles()
            for p in profiles:
                options.append((f"funnel: {p}", f"funnel:{p}"))
        except Exception:  # noqa: BLE001
            pass

        self._loadout_profiles = options
        sel = cast("Select[str]", self.query_one("#loadout-select", Select))
        sel.set_options(options)

    # ── refresh worker ────────────────────────────────────────────────────────

    def action_refresh(self) -> None:
        _ = self._start_refresh()

    @work(exclusive=True, thread=True)
    def _start_refresh(self) -> None:
        """Run in a worker thread so the UI stays responsive."""
        self.call_from_thread(self._set_loading, True)
        try:
            from core.status import refresh_sync

            rows = refresh_sync()
            _ = self.call_from_thread(self.post_message, RefreshComplete(rows))
        except Exception as exc:  # noqa: BLE001
            _ = self.call_from_thread(self.post_message, RefreshFailed(str(exc)))
        finally:
            self.call_from_thread(self._set_loading, False)

    def _set_loading(self, state: bool) -> None:
        self._loading = state
        overlay = self.query_one("#loading-overlay")
        if state:
            _ = overlay.add_class("visible")
        else:
            _ = overlay.remove_class("visible")

    def on_refresh_complete(self, message: RefreshComplete) -> None:
        self._rows = message.rows
        self._repopulate_table()
        status: StatusBar = self.query_one("#status-bar", StatusBar)
        status.status_text = (
            f"Loaded {len(self._rows)} servers  "
            f"(connected: {sum(1 for r in self._rows if r.status == AuthStatus.CONNECTED)}  "
            f"disabled: {sum(1 for r in self._rows if not r.enabled)}  "
            f"needs-auth: {sum(1 for r in self._rows if r.status == AuthStatus.NEEDS_AUTH)})"
        )

    def on_refresh_failed(self, message: RefreshFailed) -> None:
        status: StatusBar = self.query_one("#status-bar", StatusBar)
        status.status_text = f"[red]Refresh failed: {message.error}[/red]"

    # ── table population ──────────────────────────────────────────────────────

    def _repopulate_table(self) -> None:
        table = cast("DataTable[str]", self.query_one("#server-table", DataTable))
        _ = table.clear()
        for row in self._rows:
            sel_mark = "☑" if row.id in self._selected_ids else "☐"
            status_val = row.status.value
            badge = STATUS_BADGES.get(status_val, "? pending")
            enabled_str = ENABLED_BADGE if row.enabled else DISABLED_BADGE
            planes_str = ",".join(sorted(set(row.planes)))
            auth_str = (row.auth or "")[:23]
            _ = table.add_row(
                sel_mark,
                badge,
                row.name[:33],
                planes_str[:15],
                enabled_str,
                auth_str,
                key=row.id,
            )
        self._update_sel_label()

    def _update_sel_label(self) -> None:
        n = len(self._selected_ids)
        label: Label = self.query_one("#sel-label", Label)
        label.update(f"Selection: {n} server(s) selected")

    # ── row selection ─────────────────────────────────────────────────────────

    def _toggle_selection(self, row_key: str) -> None:
        if row_key in self._selected_ids:
            self._selected_ids.discard(row_key)
        else:
            self._selected_ids.add(row_key)
        self._refresh_row(row_key)
        self._update_sel_label()

    def _refresh_row(self, row_key: str) -> None:
        """Update just the selection column for a single row."""
        table = cast("DataTable[str]", self.query_one("#server-table", DataTable))
        sel_mark = "☑" if row_key in self._selected_ids else "☐"
        try:
            table.update_cell(row_key, "Sel", sel_mark)
        except Exception:  # noqa: BLE001
            pass

    def action_toggle_row(self) -> None:
        table = cast("DataTable[str]", self.query_one("#server-table", DataTable))
        if table.cursor_row < 0 or table.cursor_row >= len(self._rows):
            return
        row_key = self._rows[table.cursor_row].id
        self._toggle_selection(row_key)

    def action_select_all(self) -> None:
        self._selected_ids = {r.id for r in self._rows}
        self._repopulate_table()

    def action_clear_selection(self) -> None:
        # If an auth panel is showing, close it first
        for widget in self.query("#auth-panel").first().children:
            _ = widget.remove()
        self._selected_ids.clear()
        self._repopulate_table()

    @on(DataTable.RowSelected)
    def on_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.row_key and event.row_key.value:
            self._toggle_selection(str(event.row_key.value))

    # ── bulk actions ──────────────────────────────────────────────────────────

    def action_enable_selected(self) -> None:
        _ = self._bulk_toggle(enable=True)

    def action_disable_selected(self) -> None:
        _ = self._bulk_toggle(enable=False)

    @work(exclusive=False, thread=True)
    def _bulk_toggle(self, *, enable: bool) -> None:
        """Apply enable/disable to all selected servers in a worker thread."""
        if not self._selected_ids:
            return
        from core import claude_adapter
        from pathlib import Path

        claude_json = Path.home() / ".claude.json"
        project_path = str(Path.home()).replace("\\", "/")
        changed: list[str] = []
        errors: list[str] = []
        for sid in list(self._selected_ids):
            try:
                did_change = claude_adapter.set_server_disabled(
                    claude_json, project_path, sid, not enable
                )
                if did_change:
                    changed.append(sid)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{sid}: {exc}")
        # Update local model without a full refresh
        for row in self._rows:
            if row.id in self._selected_ids:
                row.enabled = enable
        verb = "enabled" if enable else "disabled"
        msg = f"Bulk {verb}: {len(changed)} changed"
        if errors:
            msg += f"  ({len(errors)} errors)"
        self.call_from_thread(self._finish_bulk, msg)

    def _finish_bulk(self, msg: str) -> None:
        status: StatusBar = self.query_one("#status-bar", StatusBar)
        status.status_text = msg
        self._repopulate_table()

    # ── authenticate ──────────────────────────────────────────────────────────

    def action_authenticate_selected(self) -> None:
        self._show_auth_info()

    def _show_auth_info(self) -> None:
        """Display auth instructions for the focused/selected server(s)."""
        target_ids = list(self._selected_ids)
        if not target_ids:
            # Use focused row
            table = cast("DataTable[str]", self.query_one("#server-table", DataTable))
            if table.cursor_row >= 0 and table.cursor_row < len(self._rows):
                target_ids = [self._rows[table.cursor_row].id]
        if not target_ids:
            return
        # Show info for the first target
        sid = target_ids[0]
        row_obj = next((r for r in self._rows if r.id == sid), None)
        planes = row_obj.planes if row_obj else ["claude"]

        auth_panel = self.query_one("#auth-panel")
        # Remove any existing modal
        for child in list(auth_panel.children):
            _ = child.remove()
        _ = auth_panel.mount(AuthInfoModal(sid, planes))

    # ── loadout actions ───────────────────────────────────────────────────────

    @on(Button.Pressed, "#btn-apply-loadout")
    def _apply_loadout(self) -> None:
        sel = cast("Select[str]", self.query_one("#loadout-select", Select))
        value = sel.value
        # Select.BLANK is falsy, so `not value` also covers the no-selection case.
        if not value:
            status: StatusBar = self.query_one("#status-bar", StatusBar)
            status.status_text = "No loadout selected."
            return
        _ = self._do_apply_loadout(str(value))

    @work(exclusive=False, thread=True)
    def _do_apply_loadout(self, loadout_key: str) -> None:
        from pathlib import Path

        claude_json = Path.home() / ".claude.json"
        project_path = str(Path.home()).replace("\\", "/")
        msg = ""

        if loadout_key == "__defaults__":
            try:
                lo = loadout_mod.read_loadout()
                changed = loadout_mod.apply_loadout_to_project(
                    lo, claude_json, project_path
                )
                msg = f"Loadout applied: {len(changed)} servers disabled"
            except Exception as exc:  # noqa: BLE001
                msg = f"Loadout error: {exc}"
        elif loadout_key.startswith("funnel:"):
            profile = loadout_key[len("funnel:") :]
            try:
                ok, out = funnel_adapter.switch_profile(profile)
                msg = f"Funnel profile '{profile}': {'ok' if ok else 'FAILED'} — {out}"
            except Exception as exc:  # noqa: BLE001
                msg = f"Funnel error: {exc}"
        else:
            msg = f"Unknown loadout key: {loadout_key}"

        self.call_from_thread(self._finish_loadout, msg)

    def _finish_loadout(self, msg: str) -> None:
        status: StatusBar = self.query_one("#status-bar", StatusBar)
        status.status_text = msg
        self.action_refresh()

    # ── toolbar buttons ───────────────────────────────────────────────────────

    @on(Button.Pressed, "#btn-refresh")
    def _btn_refresh(self) -> None:
        self.action_refresh()

    @on(Button.Pressed, "#btn-enable")
    def _btn_enable(self) -> None:
        self.action_enable_selected()

    @on(Button.Pressed, "#btn-disable")
    def _btn_disable(self) -> None:
        self.action_disable_selected()

    @on(Button.Pressed, "#btn-auth")
    def _btn_auth(self) -> None:
        self.action_authenticate_selected()


# ── entrypoint ────────────────────────────────────────────────────────────────


def main() -> None:
    app = MCPManagerApp()
    app.run()


if __name__ == "__main__":
    main()
