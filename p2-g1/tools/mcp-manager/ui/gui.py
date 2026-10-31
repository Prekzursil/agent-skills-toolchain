"""mcp-manager — native desktop GUI (PySide6).

A normal OS window (QMainWindow) that REPLACES the vim-like Textual TUI while
REUSING the existing core data/adapter layer untouched.  It never reimplements
file parsing or writes — every action dispatches to ``core.*``.

Design goals (the whole point):
- Robust: every adapter/core call is wrapped in try/except and surfaced on the
  status bar; the window must never crash on a backend error.
- Non-blocking: status/inventory fetches and write-storms run on a QThreadPool
  (QRunnable workers) so the UI never freezes.  Action buttons are disabled
  while a refresh is in flight.
- Plane-correct: Enable/Disable dispatch on each row's plane (the old TUI's
  single-plane bulk write was a real bug):
    * claude  -> core.claude_adapter.set_server_disabled (enable = disabled=False)
    * codex   -> core.codex_adapter.set_server_enabled
    * funnel  -> no per-server enable/disable (surfaced as an informational note)
- Single-backup batches: each bulk write uses ONE timestamped backup dir for the
  whole operation instead of a fresh backup per server.

Entry points:
    build_app() -> QMainWindow   # creates the QApplication if needed; no exec()
    main()      -> int           # build + exec()

Run:
    uv run python -m ui.gui          (or)   uv run python ui/gui.py
"""

from __future__ import annotations

import sys
import time
import traceback
from pathlib import Path
from typing import Callable, TypedDict, cast, final

from typing_extensions import override

# Ensure the project root (parent of this 'ui' package) is importable when this
# file is run directly as a script (python ui/gui.py).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from PySide6.QtCore import (  # noqa: E402
    QObject,
    QRunnable,
    Qt,
    QThreadPool,
    Signal,
    Slot,
)
from PySide6.QtGui import QAction, QColor  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from core.models import AuthStatus, ServerRow  # noqa: E402

# Plane labels (display order preference for the merged Plane column)
_PLANE_ORDER = ["claude", "codex", "funnel"]

# Status -> (display text, color) for the Status column
_STATUS_DISPLAY: dict[str, tuple[str, QColor]] = {
    AuthStatus.CONNECTED.value: ("connected", QColor(40, 160, 60)),
    AuthStatus.NEEDS_AUTH.value: ("needs-auth", QColor(190, 150, 0)),
    AuthStatus.FAILED.value: ("error", QColor(200, 50, 50)),
    # grey, not red: a disabled server is intentional, not an error
    AuthStatus.DISABLED.value: ("disabled", QColor(130, 130, 130)),
    AuthStatus.UNKNOWN.value: ("pending", QColor(130, 130, 130)),
}

# How to authenticate each plane (informational — core has no auth launcher).
_AUTH_HINTS: dict[str, str] = {
    "codex": "Run in a terminal:  codex mcp login <server-name>",
    "claude": "Open Claude Code and run:  /mcp  then select the server.",
    "funnel": "Run:  mcp-profile.ps1 <profile-name>  (switches the active funnel profile).",
}

_COLUMNS = ["Plane", "Name", "Status", "Enabled"]


class _ToggleSummary(TypedDict):
    """Result of a per-plane enable/disable batch."""

    changed: list[str]
    skipped: list[str]
    errors: list[str]
    funnel_skipped: list[str]


class _LoadoutSummary(TypedDict):
    """Result of applying the disabled-defaults loadout."""

    loadout: str
    count: int
    changed: list[str]


# ── Background worker plumbing (QThreadPool / QRunnable) ──────────────────────


@final
class _WorkerSignals(QObject):
    """Signals emitted from a background QRunnable. Strings/objects only —
    no widget references cross the thread boundary."""

    result = Signal(object)  # payload on success
    error = Signal(str)  # human-readable error string
    finished = Signal()  # always fires (success or error)


@final
class _Worker(QRunnable):
    """Run a plain callable on the QThreadPool, never raising into Qt.

    Any exception is caught and forwarded as an `error` string so the UI thread
    can surface it on the status bar instead of crashing the event loop.
    """

    def __init__(
        self, fn: Callable[..., object], *args: object, **kwargs: object
    ) -> None:
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self.signals = _WorkerSignals()

    @override
    @Slot()
    def run(self) -> None:  # noqa: D401 - QRunnable entry point
        try:
            payload = self._fn(*self._args, **self._kwargs)
        except Exception as exc:  # noqa: BLE001 - workers must never crash Qt
            detail = "".join(traceback.format_exception_only(type(exc), exc)).strip()
            self.signals.error.emit(detail or repr(exc))
        else:
            try:
                self.signals.result.emit(payload)
            except RuntimeError:
                # Receiver (window) was already destroyed — drop silently.
                pass
        finally:
            try:
                self.signals.finished.emit()
            except RuntimeError:
                # Signal source/receiver torn down (e.g. interpreter shutdown
                # while a worker is still in flight) — drop silently.
                pass


# ── Core-call helpers (pure functions; all run inside workers) ────────────────
#
# These import core lazily so the GUI module imports cleanly even if an
# individual adapter has a missing optional dep (e.g. tomlkit).


def _fetch_rows(project_path: str | None) -> list[ServerRow]:
    """Reuse core.status.refresh_sync — the single source of truth for the
    merged, fail-soft, cross-plane server universe."""
    from core import status

    return status.refresh_sync(project_path=project_path)


def _apply_toggle(
    rows: list[ServerRow],
    enable: bool,
    project_path: str,
) -> _ToggleSummary:
    """Enable/disable each row, dispatching on its plane. Runs in a worker.

    Returns a summary dict: {changed, skipped, errors, funnel_skipped}.
    Uses ONE timestamped backup dir for the whole batch (single-backup intent),
    reusing the existing safe-write adapters — no logic is reimplemented here.
    """
    from pathlib import Path as _Path

    from core import claude_adapter, codex_adapter

    claude_json = _Path.home() / ".claude.json"
    codex_toml = _Path.home() / ".codex" / "config.toml"

    ts = int(time.time())
    claude_backup_dir = claude_json.parent / ".mcp-manager-backups" / f"batch-{ts}"

    changed: list[str] = []
    skipped: list[str] = []
    errors: list[str] = []
    funnel_skipped: list[str] = []

    for row in rows:
        planes = set(row.planes)
        handled = False

        if "claude" in planes:
            handled = True
            try:
                # enable == not disabled. _mtime_check on the first write per
                # batch only would still backup per call, so we pin a single
                # batch backup_dir and disable per-call mtime churn.
                did = claude_adapter.set_server_disabled(
                    claude_json,
                    project_path,
                    row.id,
                    disabled=not enable,
                    backup_dir=claude_backup_dir,
                    _mtime_check=False,
                )
                (changed if did else skipped).append(f"claude:{row.id}")
            except Exception as exc:  # noqa: BLE001
                errors.append(f"claude:{row.id}: {exc}")

        if "codex" in planes:
            handled = True
            try:
                did = codex_adapter.set_server_enabled(
                    codex_toml,
                    row.name,
                    enabled=enable,
                    backup=True,
                )
                (changed if did else skipped).append(f"codex:{row.name}")
            except KeyError:
                errors.append(f"codex:{row.name}: not found in config.toml")
            except ImportError:
                errors.append("codex: tomlkit not installed (uv add tomlkit)")
            except Exception as exc:  # noqa: BLE001
                errors.append(f"codex:{row.name}: {exc}")

        if "funnel" in planes and not handled:
            # Funnel servers have no per-server enable/disable — only profile
            # switching. Surface, don't silently no-op (the old TUI bug).
            funnel_skipped.append(row.name)

    return {
        "changed": changed,
        "skipped": skipped,
        "errors": errors,
        "funnel_skipped": funnel_skipped,
    }


def _apply_loadout(project_path: str) -> _LoadoutSummary:
    """Reuse core.loadout to apply the disabled-defaults loadout with a single
    batch backup dir. Runs in a worker."""
    from pathlib import Path as _Path

    from core import loadout as loadout_mod

    claude_json = _Path.home() / ".claude.json"
    ts = int(time.time())
    backup_dir = claude_json.parent / ".mcp-manager-backups" / f"loadout-{ts}"

    ld = loadout_mod.read_loadout()
    changed = loadout_mod.apply_loadout_to_project(
        ld,
        claude_json,
        project_path,
        backup_dir=backup_dir,
    )
    return {"loadout": ld.name, "count": len(ld.disabled_ids), "changed": changed}


def _list_funnel_profiles() -> list[str]:
    from core import funnel_adapter

    return funnel_adapter.list_profiles()


def _switch_funnel_profile(name: str) -> tuple[bool, str]:
    from core import funnel_adapter

    return funnel_adapter.switch_profile(name)


def _preset_names() -> list[str]:
    """Selectable preset names ('core' first, then the named bundles)."""
    from core import presets

    return ["core", *presets.read_catalog().names()]


class _PresetApplySummary(TypedDict):
    """Result of applying a preset selection to the current project."""

    preset: str
    disabled: int
    enabled: int
    unknown: list[str]
    unmatched: list[str]


def _apply_preset_bg(
    selected: list[str], inventory_ids: list[str], project_path: str
) -> _PresetApplySummary:
    """Resolve + apply a preset selection for one project (runs in a worker).

    Writes ONLY the project's disabledMcpServers via the safe path. Servers
    outside the supplied inventory are never touched. Takes effect NEXT session.
    """
    from pathlib import Path as _Path

    from core import presets

    claude_json = _Path.home() / ".claude.json"
    ts = int(time.time())
    backup_dir = claude_json.parent / ".mcp-manager-backups" / f"preset-{ts}"
    result = presets.apply_selection(
        selected, inventory_ids, claude_json, project_path, backup_dir=backup_dir
    )
    return {
        "preset": ", ".join(selected),
        "disabled": len(result.newly_disabled),
        "enabled": len(result.newly_enabled),
        "unknown": result.resolve.unknown_presets,
        "unmatched": result.resolve.unmatched_members,
    }


# paste state -> display AuthStatus
_PASTE_STATUS: dict[str, AuthStatus] = {
    "connected": AuthStatus.CONNECTED,
    "failed": AuthStatus.FAILED,
    "needs_auth": AuthStatus.NEEDS_AUTH,
    # a pasted panel that says 'disabled' means intentional, not pending
    "disabled": AuthStatus.DISABLED,
    "unknown": AuthStatus.UNKNOWN,
}


def _rows_from_paste(text: str) -> list[ServerRow]:
    """Parse a pasted /mcp dump into ServerRow objects for the table."""
    from core import paste_parse

    rows: list[ServerRow] = []
    for srv in paste_parse.parse_mcp_panel(text):
        rows.append(
            ServerRow(
                id=srv.name,
                name=srv.name,
                planes=["claude"],
                enabled=srv.enabled,
                status=_PASTE_STATUS.get(srv.state, AuthStatus.UNKNOWN),
                auth=srv.state,
            )
        )
    return rows


@final
class _PasteDialog(QDialog):
    """A modal text area for pasting a raw ``/mcp`` panel dump."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Paste /mcp server list")
        self.resize(560, 460)
        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "Paste the text of Claude Code's /mcp panel below.\n"
                "Lines like 'apktool-mcp · ✔ connected · 16 tools' are parsed "
                "into an inventory you can bulk-apply a preset against."
            )
        )
        self._edit = QPlainTextEdit()
        self._edit.setPlaceholderText("apktool-mcp · ✔ connected · 16 tools ...")
        layout.addWidget(self._edit)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        _ = buttons.accepted.connect(self.accept)
        _ = buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def text(self) -> str:
        return self._edit.toPlainText()


# ── Main window ───────────────────────────────────────────────────────────────


@final
class McpManagerWindow(QMainWindow):
    """The desktop window: a server table + a toolbar of explicit actions."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("MCP Manager")
        self.resize(960, 620)

        self._pool = QThreadPool.globalInstance()
        self._rows: list[ServerRow] = []
        self._busy = False
        # project_path key used by core.claude_adapter. Key off the LAUNCH cwd
        # (what the enforce hook uses), NOT Path.home() — otherwise "this
        # project" edits land on the wrong ~/.claude.json key.
        self._project_path = str(Path.cwd()).replace("\\", "/")
        # When set, a pasted /mcp dump is the inventory instead of live rows.
        self._pasted_inventory: list[str] | None = None

        self._build_ui()
        # Kick off the first refresh after the window is shown so an empty table
        # never looks "hung" — the status bar says "Loading…".
        self.refresh()

    # ── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        toolbar = QToolBar("Actions")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        self._actions: dict[str, QAction] = {}
        for label, handler, tip in (
            ("Enable", self.on_enable, "Enable selected servers (per plane)"),
            ("Disable", self.on_disable, "Disable selected servers (per plane)"),
            ("Refresh", self.refresh, "Reload the server universe across all planes"),
            (
                "Apply Loadout",
                self.on_apply_loadout,
                "Disable every server in the saved loadout-defaults",
            ),
            (
                "Funnel Profile",
                self.on_funnel_profile,
                "Switch the active mcp-funnel profile",
            ),
            (
                "Launch Auth",
                self.on_launch_auth,
                "Show how to authenticate the selected server",
            ),
        ):
            act = QAction(label, self)
            act.setToolTip(tip)
            _ = act.triggered.connect(handler)
            toolbar.addAction(act)
            self._actions[label] = act

        # ── Claude-plane preset bar (bulk enable-list apply) ─────────────────
        preset_bar = QToolBar("Presets")
        preset_bar.setMovable(False)
        self.addToolBarBreak()
        self.addToolBar(preset_bar)
        preset_bar.addWidget(QLabel(" Preset: "))
        self._preset_combo = QComboBox()
        self._reload_presets()
        preset_bar.addWidget(self._preset_combo)
        for label, handler, tip in (
            (
                "Apply Preset",
                self.on_apply_preset,
                "Enable this preset's servers for THIS project (disables the "
                "rest). Applies NEXT session — restart to take effect.",
            ),
            (
                "Save Selection",
                self.on_save_preset,
                "Save the selected rows as a new named preset (enable-list)",
            ),
            (
                "Paste /mcp List",
                self.on_paste_list,
                "Paste a raw /mcp panel dump to use as the inventory",
            ),
            (
                "Try Live (experimental)",
                self.on_try_live,
                "EXPERIMENTAL: drive the /mcp TUI via keystrokes — fragile, "
                "may fail. Requires a pasted list + target window.",
            ),
        ):
            act = QAction(label, self)
            act.setToolTip(tip)
            _ = act.triggered.connect(handler)
            preset_bar.addAction(act)
            self._actions[label] = act

        # Central widget: search + header label + table.
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 4)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Filter servers (fuzzy)…")
        self._search.setClearButtonEnabled(True)
        _ = self._search.textChanged.connect(self._apply_filter)
        layout.addWidget(self._search)

        self._summary = QLabel("Loading…")
        self._summary.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self._summary)

        self.table = QTableWidget(0, len(_COLUMNS))
        self.table.setHorizontalHeaderLabels(_COLUMNS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table)

        self.setCentralWidget(central)

        self.setStatusBar(QStatusBar())
        self._set_status("Ready")

    # ── Small helpers ────────────────────────────────────────────────────────

    def _set_status(self, text: str) -> None:
        # statusBar().showMessage takes a plain string — no markup, can't crash.
        self.statusBar().showMessage(text)

    def _set_busy(self, busy: bool) -> None:
        """Disable/enable the action buttons while a worker is in flight."""
        self._busy = busy
        for act in self._actions.values():
            act.setEnabled(not busy)

    def _selected_rows(self) -> list[ServerRow]:
        """Return the ServerRow objects backing the selected table rows."""
        out: list[ServerRow] = []
        for idx in sorted({i.row() for i in self.table.selectedIndexes()}):
            if 0 <= idx < len(self._rows):
                out.append(self._rows[idx])
        return out

    def _plane_label(self, row: ServerRow) -> str:
        planes = sorted(
            set(row.planes),
            key=lambda p: (
                _PLANE_ORDER.index(p) if p in _PLANE_ORDER else len(_PLANE_ORDER)
            ),
        )
        return "+".join(planes) if planes else "?"

    # ── Table population ─────────────────────────────────────────────────────

    def _populate(self, rows: list[ServerRow]) -> None:
        """Always-repopulate (no fragile per-cell update path). rows is the
        authoritative model; row index == self._rows index."""
        self._rows = list(rows)
        self.table.setRowCount(len(self._rows))
        connected = enabled = 0
        for r, row in enumerate(self._rows):
            plane_item = QTableWidgetItem(self._plane_label(row))
            name_item = QTableWidgetItem(row.name)
            name_item.setToolTip(row.id)

            disp, color = _STATUS_DISPLAY.get(
                row.status.value, (row.status.value, QColor(130, 130, 130))
            )
            status_item = QTableWidgetItem(disp)
            status_item.setForeground(color)
            if row.auth:
                status_item.setToolTip(row.auth)
            if row.status == AuthStatus.CONNECTED:
                connected += 1

            enabled_item = QTableWidgetItem("enabled" if row.enabled else "disabled")
            if row.enabled:
                enabled += 1
            else:
                enabled_item.setForeground(QColor(150, 150, 150))

            for col, item in enumerate(
                (plane_item, name_item, status_item, enabled_item)
            ):
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(r, col, item)

        self._summary.setText(
            f"{len(self._rows)} servers   |   {enabled} enabled   |   "
            + f"{connected} connected"
        )
        self._apply_filter()

    # ── Fuzzy filter ─────────────────────────────────────────────────────────

    def _apply_filter(self, *_args: object) -> None:
        """Hide table rows whose name doesn't match the search box (fuzzy)."""
        from core import presets

        query = self._search.text()
        visible = set(presets.fuzzy_filter(query, [r.name for r in self._rows]))
        for i, row in enumerate(self._rows):
            self.table.setRowHidden(i, row.name not in visible)

    # ── Refresh (background) ─────────────────────────────────────────────────

    def refresh(self, *_args: object) -> None:
        if self._busy:
            return
        self._set_busy(True)
        self._set_status("Refreshing… (querying claude / codex / funnel)")
        worker = _Worker(_fetch_rows, self._project_path)
        _ = worker.signals.result.connect(self._on_refresh_result)
        _ = worker.signals.error.connect(self._on_refresh_error)
        _ = worker.signals.finished.connect(lambda: self._set_busy(False))
        self._pool.start(worker)

    @Slot(object)
    def _on_refresh_result(self, rows: object) -> None:
        try:
            self._populate(cast("list[ServerRow]", rows))
            self._set_status(f"Loaded {len(self._rows)} servers.")
        except Exception as exc:  # noqa: BLE001 - never crash on render
            self._set_status(f"Render error: {exc}")

    @Slot(str)
    def _on_refresh_error(self, error: str) -> None:
        self._set_status(f"Refresh failed: {error}")
        self._summary.setText("Refresh failed — see status bar.")

    # ── Enable / Disable (background, per-plane dispatch) ─────────────────────

    def on_enable(self, *_args: object) -> None:
        self._toggle(enable=True)

    def on_disable(self, *_args: object) -> None:
        self._toggle(enable=False)

    def _toggle(self, *, enable: bool) -> None:
        if self._busy:
            return
        rows = self._selected_rows()
        if not rows:
            self._set_status("No servers selected.")
            return
        verb = "Enabling" if enable else "Disabling"
        self._set_busy(True)
        self._set_status(f"{verb} {len(rows)} server(s)…")
        worker = _Worker(_apply_toggle, rows, enable, self._project_path)
        _ = worker.signals.result.connect(self._on_toggle_result)
        _ = worker.signals.error.connect(self._on_toggle_error)
        # After a write, always re-refresh so the table reflects real state.
        _ = worker.signals.finished.connect(self._after_write)
        self._pool.start(worker)

    @Slot(object)
    def _on_toggle_result(self, summary: object) -> None:
        s = cast("_ToggleSummary", summary)
        changed = len(s["changed"])
        skipped = len(s["skipped"])
        errors = s["errors"]
        funnel = s["funnel_skipped"]
        parts = [f"{changed} changed", f"{skipped} no-op"]
        if errors:
            parts.append(f"{len(errors)} error(s)")
        if funnel:
            parts.append(f"{len(funnel)} funnel (no per-server toggle)")
        self._set_status("Write complete: " + ", ".join(parts))
        if errors:
            _ = QMessageBox.warning(
                self, "Some writes failed", "\n".join(str(e) for e in errors[:20])
            )

    @Slot(str)
    def _on_toggle_error(self, error: str) -> None:
        self._set_status(f"Write failed: {error}")

    def _after_write(self) -> None:
        # _set_busy(False) happens via refresh() flow; trigger a reload.
        self._set_busy(False)
        self.refresh()

    # ── Apply loadout (background) ───────────────────────────────────────────

    def on_apply_loadout(self, *_args: object) -> None:
        if self._busy:
            return
        confirm = QMessageBox.question(
            self,
            "Apply loadout",
            "Disable every server listed in the saved loadout-defaults "
            + "for this project?\n\nA timestamped backup of ~/.claude.json is "
            + "written first.",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self._set_busy(True)
        self._set_status("Applying loadout…")
        worker = _Worker(_apply_loadout, self._project_path)
        _ = worker.signals.result.connect(self._on_loadout_result)
        _ = worker.signals.error.connect(self._on_toggle_error)
        _ = worker.signals.finished.connect(self._after_write)
        self._pool.start(worker)

    @Slot(object)
    def _on_loadout_result(self, summary: object) -> None:
        s = cast("_LoadoutSummary", summary)
        self._set_status(
            f"Loadout '{s['loadout']}' applied: "
            + f"{len(s['changed'])} newly disabled "
            + f"(of {s['count']} in loadout)."
        )

    # ── Named presets (Claude-plane bulk enable-list) ────────────────────────

    def _reload_presets(self) -> None:
        self._preset_combo.clear()
        try:
            self._preset_combo.addItems(_preset_names())
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"Could not load presets: {exc}")

    def _current_inventory_ids(self) -> list[str]:
        """Inventory to resolve against: a pasted dump if present, else live."""
        if self._pasted_inventory is not None:
            return list(self._pasted_inventory)
        return [r.id for r in self._rows]

    def on_apply_preset(self, *_args: object) -> None:
        if self._busy:
            return
        name = self._preset_combo.currentText()
        if not name:
            self._set_status("No preset selected.")
            return
        inventory = self._current_inventory_ids()
        if not inventory:
            self._set_status("No inventory — Refresh or paste a /mcp list first.")
            return
        source = "pasted list" if self._pasted_inventory is not None else "live rows"
        confirm = QMessageBox.question(
            self,
            "Apply preset",
            f"Enable preset '{name}' for this project (using {source}, "
            + f"{len(inventory)} servers)?\n\n"
            + "Servers not in the preset are DISABLED. A timestamped backup of "
            + "~/.claude.json is written first.\n\n"
            + "APPLIES NEXT SESSION — restart Claude Code to take effect.",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self._set_busy(True)
        self._set_status(f"Applying preset '{name}'…")
        worker = _Worker(_apply_preset_bg, [name], inventory, self._project_path)
        _ = worker.signals.result.connect(self._on_preset_result)
        _ = worker.signals.error.connect(self._on_toggle_error)
        _ = worker.signals.finished.connect(self._after_write)
        self._pool.start(worker)

    @Slot(object)
    def _on_preset_result(self, summary: object) -> None:
        s = cast("_PresetApplySummary", summary)
        if s["unknown"]:
            self._set_status("Unknown preset(s): " + ", ".join(s["unknown"]))
            return
        msg = (
            f"Preset '{s['preset']}' applied: {s['disabled']} disabled, "
            + f"{s['enabled']} enabled. APPLIES NEXT SESSION — restart Claude Code."
        )
        self._set_status(msg)

    def on_save_preset(self, *_args: object) -> None:
        rows = self._selected_rows()
        if not rows:
            self._set_status("Select the servers to save as a preset first.")
            return
        name, ok = QInputDialog.getText(self, "Save preset", "Preset name:")
        if not ok or not name.strip():
            return
        members = [r.name for r in rows]
        try:
            from core import presets

            changed = presets.save_preset(name.strip(), members)
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"Could not save preset: {exc}")
            return
        self._reload_presets()
        verb = "saved" if changed else "unchanged"
        self._set_status(f"Preset '{name.strip()}' {verb} ({len(members)} servers).")

    def on_paste_list(self, *_args: object) -> None:
        dialog = _PasteDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        text = dialog.text()
        try:
            rows = _rows_from_paste(text)
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"Paste parse failed: {exc}")
            return
        if not rows:
            self._set_status("No servers parsed from the pasted list.")
            return
        self._pasted_inventory = [r.id for r in rows]
        self._populate(rows)
        self._set_status(
            f"Using pasted inventory ({len(rows)} servers). Pick a preset and "
            + "Apply — changes take effect NEXT session (restart)."
        )

    def on_try_live(self, *_args: object) -> None:
        _ = QMessageBox.warning(
            self,
            "Experimental — fragile, may fail",
            "This drives the interactive /mcp TUI with BLIND keystrokes. The "
            "list is arrows-only and scrolling; there is NO reliable success "
            "signal. It can mis-toggle. This is a best-effort escape hatch, not "
            "a reliable path — verify /mcp manually afterwards.",
        )
        if self._pasted_inventory is None:
            self._set_status("Paste a /mcp list first (Try Live needs its order).")
            return
        name = self._preset_combo.currentText()
        window_title, ok = QInputDialog.getText(
            self, "Target window", "Terminal window title (partial):"
        )
        if not ok or not window_title.strip():
            return
        try:
            from core import live_macro, paste_parse, presets

            # Rebuild ParsedServer order from the current table rows.
            servers = [
                paste_parse.ParsedServer(
                    name=r.name,
                    state="disabled" if not r.enabled else "connected",
                )
                for r in self._rows
            ]
            resolved = presets.resolve_disabled(
                presets.read_catalog(), [name], self._pasted_inventory
            )
            plan = live_macro.plan_navigation(servers, set(resolved.to_enable))
            ok2, msg = live_macro.run_macro(
                plan,
                window_title.strip(),
                focuser=live_macro.default_focuser,
                sender=(lambda _step: None),
                dry_run=True,
            )
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"Try Live failed to plan: {exc}")
            return
        _ = QMessageBox.information(
            self,
            "Try Live — dry run",
            f"{msg}\n\nPlanned {len(plan)} keystroke step(s).\n\n"
            + "This was a DRY RUN (nothing sent). Live sending is CLI-only "
            + "(app.py try-live --apply) and remains experimental.",
        )
        self._set_status(f"Try Live planned {len(plan)} step(s) (dry run).")

    # ── Funnel profile switch (background) ───────────────────────────────────

    def on_funnel_profile(self, *_args: object) -> None:
        if self._busy:
            return
        try:
            profiles = _list_funnel_profiles()
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"Could not list funnel profiles: {exc}")
            return
        if not profiles:
            self._set_status("No funnel profiles found.")
            return
        name, ok = QInputDialog.getItem(
            self, "Switch funnel profile", "Profile:", profiles, 0, False
        )
        if not ok or not name:
            return
        self._set_busy(True)
        self._set_status(f"Switching funnel profile to '{name}'…")
        worker = _Worker(_switch_funnel_profile, name)
        _ = worker.signals.result.connect(self._on_funnel_result)
        _ = worker.signals.error.connect(self._on_toggle_error)
        _ = worker.signals.finished.connect(lambda: self._set_busy(False))
        self._pool.start(worker)

    @Slot(object)
    def _on_funnel_result(self, payload: object) -> None:
        try:
            ok, msg = cast("tuple[bool, str]", payload)
        except Exception:  # noqa: BLE001
            ok, msg = False, str(payload)
        prefix = "Funnel profile switched" if ok else "Funnel switch failed"
        self._set_status(f"{prefix}: {msg}"[:300])

    # ── Launch auth (informational; core has no auth launcher) ───────────────

    def on_launch_auth(self, *_args: object) -> None:
        rows = self._selected_rows()
        if not rows:
            self._set_status("Select a server to see its auth instructions.")
            return
        row = rows[0]
        lines = [
            f"Server: {row.name}",
            f"ID: {row.id}",
            f"Status: {row.status.value}",
            "",
        ]
        for plane in sorted(set(row.planes)):
            hint = _AUTH_HINTS.get(plane, f"(no auth hint for plane '{plane}')")
            lines.append(f"[{plane}] {hint}")
        lines.append("")
        lines.append(
            "Note: this manager cannot complete OAuth flows. Run the command "
            + "above in a terminal, then press Refresh."
        )
        _ = QMessageBox.information(self, "How to authenticate", "\n".join(lines))
        self._set_status(f"Auth instructions shown for '{row.name}'.")


# ── Public entry points ───────────────────────────────────────────────────────


def build_app() -> McpManagerWindow:
    """Create the QApplication (if one doesn't exist) and the main window.

    Returns the window WITHOUT calling exec(). Safe to call headless under
    QT_QPA_PLATFORM=offscreen for smoke tests.
    """
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv if hasattr(sys, "argv") else [])
    window = McpManagerWindow()
    return window


def main() -> int:
    """Build the window, show it, and run the Qt event loop."""
    app = QApplication.instance() or QApplication(sys.argv)
    window = build_app()
    window.show()
    return int(app.exec())


if __name__ == "__main__":
    sys.exit(main())
