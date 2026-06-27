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
from typing import Any, Callable

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
    QHeaderView,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
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
    AuthStatus.UNKNOWN.value: ("pending", QColor(130, 130, 130)),
}

# How to authenticate each plane (informational — core has no auth launcher).
_AUTH_HINTS: dict[str, str] = {
    "codex": "Run in a terminal:  codex mcp login <server-name>",
    "claude": "Open Claude Code and run:  /mcp  then select the server.",
    "funnel": "Run:  mcp-profile.ps1 <profile-name>  (switches the active funnel profile).",
}

_COLUMNS = ["Plane", "Name", "Status", "Enabled"]


# ── Background worker plumbing (QThreadPool / QRunnable) ──────────────────────


class _WorkerSignals(QObject):
    """Signals emitted from a background QRunnable. Strings/objects only —
    no widget references cross the thread boundary."""

    result = Signal(object)  # payload on success
    error = Signal(str)  # human-readable error string
    finished = Signal()  # always fires (success or error)


class _Worker(QRunnable):
    """Run a plain callable on the QThreadPool, never raising into Qt.

    Any exception is caught and forwarded as an `error` string so the UI thread
    can surface it on the status bar instead of crashing the event loop.
    """

    def __init__(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self.signals = _WorkerSignals()

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
) -> dict[str, Any]:
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


def _apply_loadout(project_path: str) -> dict[str, Any]:
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


# ── Main window ───────────────────────────────────────────────────────────────


class McpManagerWindow(QMainWindow):
    """The desktop window: a server table + a toolbar of explicit actions."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("MCP Manager")
        self.resize(960, 620)

        self._pool = QThreadPool.globalInstance()
        self._rows: list[ServerRow] = []
        self._busy = False
        # project_path key used by core.claude_adapter (mirrors the TUI default)
        self._project_path = str(Path.home()).replace("\\", "/")

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
            act.triggered.connect(handler)
            toolbar.addAction(act)
            self._actions[label] = act

        # Central widget: header label + table.
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 4)

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
            f"{connected} connected"
        )

    # ── Refresh (background) ─────────────────────────────────────────────────

    def refresh(self, *_: Any) -> None:
        if self._busy:
            return
        self._set_busy(True)
        self._set_status("Refreshing… (querying claude / codex / funnel)")
        worker = _Worker(_fetch_rows, self._project_path)
        worker.signals.result.connect(self._on_refresh_result)
        worker.signals.error.connect(self._on_refresh_error)
        worker.signals.finished.connect(lambda: self._set_busy(False))
        self._pool.start(worker)

    @Slot(object)
    def _on_refresh_result(self, rows: object) -> None:
        try:
            self._populate(list(rows))  # pyright: ignore[reportArgumentType]
            self._set_status(f"Loaded {len(self._rows)} servers.")
        except Exception as exc:  # noqa: BLE001 - never crash on render
            self._set_status(f"Render error: {exc}")

    @Slot(str)
    def _on_refresh_error(self, error: str) -> None:
        self._set_status(f"Refresh failed: {error}")
        self._summary.setText("Refresh failed — see status bar.")

    # ── Enable / Disable (background, per-plane dispatch) ─────────────────────

    def on_enable(self, *_: Any) -> None:
        self._toggle(enable=True)

    def on_disable(self, *_: Any) -> None:
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
        worker.signals.result.connect(self._on_toggle_result)
        worker.signals.error.connect(self._on_toggle_error)
        # After a write, always re-refresh so the table reflects real state.
        worker.signals.finished.connect(self._after_write)
        self._pool.start(worker)

    @Slot(object)
    def _on_toggle_result(self, summary: object) -> None:
        s: dict[str, Any] = summary  # pyright: ignore[reportAssignmentType]
        changed = len(s.get("changed", []))
        skipped = len(s.get("skipped", []))
        errors = s.get("errors", [])
        funnel = s.get("funnel_skipped", [])
        parts = [f"{changed} changed", f"{skipped} no-op"]
        if errors:
            parts.append(f"{len(errors)} error(s)")
        if funnel:
            parts.append(f"{len(funnel)} funnel (no per-server toggle)")
        self._set_status("Write complete: " + ", ".join(parts))
        if errors:
            QMessageBox.warning(
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

    def on_apply_loadout(self, *_: Any) -> None:
        if self._busy:
            return
        confirm = QMessageBox.question(
            self,
            "Apply loadout",
            "Disable every server listed in the saved loadout-defaults "
            "for this project?\n\nA timestamped backup of ~/.claude.json is "
            "written first.",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self._set_busy(True)
        self._set_status("Applying loadout…")
        worker = _Worker(_apply_loadout, self._project_path)
        worker.signals.result.connect(self._on_loadout_result)
        worker.signals.error.connect(self._on_toggle_error)
        worker.signals.finished.connect(self._after_write)
        self._pool.start(worker)

    @Slot(object)
    def _on_loadout_result(self, summary: object) -> None:
        s: dict[str, Any] = summary  # pyright: ignore[reportAssignmentType]
        self._set_status(
            f"Loadout '{s.get('loadout')}' applied: "
            f"{len(s.get('changed', []))} newly disabled "
            f"(of {s.get('count', 0)} in loadout)."
        )

    # ── Funnel profile switch (background) ───────────────────────────────────

    def on_funnel_profile(self, *_: Any) -> None:
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
        worker.signals.result.connect(self._on_funnel_result)
        worker.signals.error.connect(self._on_toggle_error)
        worker.signals.finished.connect(lambda: self._set_busy(False))
        self._pool.start(worker)

    @Slot(object)
    def _on_funnel_result(self, payload: object) -> None:
        try:
            ok, msg = payload  # pyright: ignore[reportGeneralTypeIssues]
        except Exception:  # noqa: BLE001
            ok, msg = False, str(payload)
        prefix = "Funnel profile switched" if ok else "Funnel switch failed"
        self._set_status(f"{prefix}: {msg}"[:300])

    # ── Launch auth (informational; core has no auth launcher) ───────────────

    def on_launch_auth(self, *_: Any) -> None:
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
            "above in a terminal, then press Refresh."
        )
        QMessageBox.information(self, "How to authenticate", "\n".join(lines))
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
