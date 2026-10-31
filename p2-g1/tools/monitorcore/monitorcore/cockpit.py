"""``cockpit`` — the interactive drill-down driver + the read-only ``--once`` export lane.

Ties WU5 (nav/view), WU6 (stall/blocked) and WU8 (--once + push) into one runnable board:

* :func:`run_interactive` is the keystroke-driven loop — render the drillable frame, block
  on ONE keypress, fold it through :func:`monitorcore.nav.apply`, repeat until quit. Every
  side effect is an injected seam (``read_key`` / ``write`` / ``clock`` / ``cols_fn`` /
  ``mtime_fn``), so the loop is fully covered without a real terminal; the raw ``msvcrt``
  getch and the real paint are the ONLY ``pragma: no cover`` shells (the ``codex_tail``
  pattern), and both dodge Linux CI via ``importlib`` like the existing modules.
* :func:`interactive_supported` is the DEGRADATION predicate: the single-key loop needs a
  real TTY and a plain console — under Windows Terminal / ConPTY (``WT_SESSION``) or the
  VS Code integrated terminal a raw getch is unreliable, so :func:`main` falls back to the
  read-only ``--once`` frame there (WU5's "degrades to --once under wt").
* :func:`stall_marks` is the WU6 integration: two mechanically-independent signals — the
  source file's mtime (filesystem) and a cross-poll content-freeze (:class:`~monitorcore
  .stall.StallTracker`) — feed :func:`~monitorcore.stall.classify_condition`, and only an
  amber inference (STALL / BLOCKED) becomes a marker. A single ``--once`` snapshot cannot
  corroborate a stall, so ``--once`` shows only fact-level state.
* :func:`main` is the CLI: ``--once`` (or a non-interactive terminal) renders one frame and
  optionally fires a ``--notify`` push; otherwise it drills. NO in-chat live board.

Stdlib-only (``importlib`` for the Windows-only console bits), so it vendors cleanly.
"""

from __future__ import annotations

import argparse
import importlib
import os
import subprocess
import sys
import time
from collections.abc import Callable, Iterable, Sequence

from .ansi_screen import paint, render_frame, stdout
from .codex_source import CodexPayload, CodexSource
from .codex_tail import CodexThread
from .contract import Snapshot
from .group_tree import derive_groups
from .nav import ViewState, apply
from .stall import Condition, StallSignals, StallTracker, classify_condition
from .view import render_view
from .liveness import classify_agent

PROGRAM_PANE_ID = "program"
BASELINE_PANE_IDS = (
    "codex",
    "agents",
    "workflows",
    "databricks",
    "mcp",
)
EXISTING_PANE_IDS = (
    "codex",
    "agents",
    "workflows",
    "databricks",
    "mcp",
    PROGRAM_PANE_ID,
)
CONTROL_PLANE_PANES = frozenset({"codex", "agents", "workflows", "databricks", "mcp"})


class Cockpit:
    def __init__(self, root: object | None = None) -> None:
        self.root = root

    def pane_ids(self) -> tuple[str, ...]:
        return EXISTING_PANE_IDS

    def is_control_plane(self, pane_id: str) -> bool:
        return pane_id in CONTROL_PLANE_PANES

    # --- operator surface (TST-0114): pure ASCII, token-based, NO_COLOR-safe ---

    def render_pane(self, pane_id: str) -> str:
        return f"[{pane_id}] read-only frame: no live rows in this snapshot"

    def render_status_line(
        self, *, theme: str = "dark", color: bool | None = None
    ) -> str:
        from .operator_surface import THEMES as _THEMES

        if theme not in _THEMES:
            raise KeyError(f"unknown theme {theme!r}")
        focused = self.pane_ids()[0]
        plain = f"> {focused} [FOCUS] [OK] theme={theme} panes={len(self.pane_ids())}"
        if color is None:
            color = not os.environ.get("NO_COLOR")
        if not color:
            return plain
        colored = plain.replace("[FOCUS]", "\x1b[33m[FOCUS]\x1b[0m")
        return colored.replace("[OK]", "\x1b[32m[OK]\x1b[0m")

    def render_screen_reader(self) -> str:
        from .operator_surface import keyboard_map as _keyboard_map

        panes = self.pane_ids()
        keys = _keyboard_map(list(panes))
        key_desc = " ".join(f"{pane}={key}" for pane, key in keys.items())
        lines = [
            f"label: focused_pane value: {panes[0]}",
            "label: theme value: dark",
            "label: events value: 0 (read-only frame)",
            "label: receipts value: 0 (read-only frame)",
            "label: status value: OK",
            f"label: keyboard_map value: {key_desc}",
        ]
        return "\n".join(lines)

    def render(self) -> dict:
        agents = []
        source = getattr(self, "source", None)
        rows = []
        if source is not None and hasattr(source, "snapshot"):
            rows = list(source.snapshot())
        elif source is not None and hasattr(source, "agents"):
            rows = list(source.agents)
        classified = [classify_agent(a) for a in rows]
        lines = [f"{row.get('id')}={row.get('state')}" for row in classified]
        return {
            "panes": [
                {
                    "id": "agentmon",
                    "lines": lines,
                    "liveness": {
                        "mtime_only_stall_banned": True,
                        "agents": classified,
                    },
                }
            ]
        }


def deployed_cockpit(source=None, **kwargs):
    c = Cockpit()
    c.source = source
    return c


__all__ = [
    "Cockpit",
    "deployed_cockpit",
    "EXISTING_PANE_IDS",
    "PROGRAM_PANE_ID",
    "decode_key",
    "interactive_supported",
    "main",
    "notify",
    "once_frame",
    "push_text",
    "run_interactive",
    "stall_marks",
]

_MARK = {Condition.STALLED: "STALL", Condition.BLOCKED: "BLOCKED"}


def _mtime(path: str) -> float | None:
    """The file's mtime, or ``None`` when it cannot be read (a fresh / absent stream file)."""
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


def interactive_supported(
    *, is_tty: bool, wt_session: str | None, term_program: str | None
) -> bool:
    """Whether the plain-console single-key drill loop is usable (else degrade to --once).

    Requires a real TTY; degrades under Windows Terminal / ConPTY (``WT_SESSION`` set) and
    the VS Code integrated terminal (also ConPTY), where a raw ``msvcrt`` getch is unreliable.
    """
    if not is_tty:
        return False
    if wt_session:
        return False
    if term_program == "vscode":
        return False
    return True


def _supported() -> bool:  # pragma: no cover - reads the real env + tty
    return interactive_supported(
        is_tty=sys.stdout.isatty(),
        wt_session=os.environ.get("WT_SESSION"),
        term_program=os.environ.get("TERM_PROGRAM"),
    )


def _blocked(thread: CodexThread) -> bool:
    """An idle thread whose newest event is still 'running' = WAITING (blocked, not frozen).

    Kept distinct from a stall: the in-flight event never completed while the thread went
    quiet, which reads as blocked-on-input rather than dead.
    """
    return (
        thread.status == "idle"
        and bool(thread.events)
        and thread.events[-1].status == "running"
    )


def _fingerprint(thread: CodexThread) -> tuple[float, int, int, int]:
    """A cheap content fingerprint; unchanged across polls ⇒ the content has frozen."""
    return (thread.last_ts, thread.tokens_total, thread.tool_count, len(thread.events))


def stall_marks(
    tracker: StallTracker,
    threads: Iterable[CodexThread],
    now: float,
    *,
    stale_s: float,
    mtime_fn: Callable[[str], float | None] = _mtime,
) -> dict[str, str]:
    """Per-thread condition markers from WU6's two-signal classifier.

    Signal 1 (filesystem): the source file's mtime is stale past ``stale_s`` (or unreadable).
    Signal 2 (content): the fingerprint has frozen across ``>= 2`` polls (via ``tracker``).
    Only an amber inference (STALL / BLOCKED) yields a marker — a fact-level abort is red via
    the group tree, and active / idle carry none.
    """
    marks: dict[str, str] = {}
    for thread in threads:
        mt = mtime_fn(thread.path)
        mtime_stale = mt is None or (now - mt) > stale_s
        frozen = tracker.observe(thread.key, _fingerprint(thread))
        condition = classify_condition(
            aborted=thread.aborted,
            blocked=_blocked(thread),
            active=thread.status == "running",
            signals=StallSignals(mtime_stale=mtime_stale, frozen_polls=frozen),
        )
        mark = _MARK.get(condition)
        if mark:
            marks[thread.key] = mark
    return marks


def push_text(snap: Snapshot[CodexPayload]) -> str:
    """A one-line push-notification body from the snapshot headline (already redaction-safe)."""
    return f"[codexmon] {snap.headline}"


def notify(text: str, *, runner: Callable[..., object] = subprocess.run) -> None:
    """Best-effort desktop toast of ``text`` via ``runner`` (never raises).

    The text is passed through the environment (``$env:MC_PUSH``), never interpolated into
    the PowerShell command line, so an attacker-influenceable thread label cannot inject.
    """
    print(text, flush=True)
    argv = [
        "powershell",
        "-NoProfile",
        "-Command",
        "[void][System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms');"
        "[System.Windows.Forms.MessageBox]::Show($env:MC_PUSH,'Codex cockpit')",
    ]
    try:
        runner(argv, timeout=5, env={**os.environ, "MC_PUSH": text})
    except Exception:
        pass


def once_frame(snap: Snapshot[CodexPayload], cols: int) -> list[str]:
    """The read-only single board frame for ``--once`` (no cursor, no stall corroboration)."""
    groups = derive_groups(snap.payload.threads)
    return render_view(groups, ViewState(), snap.ts, cols, cursor=False)


def decode_key(raw: str) -> str:
    """Map a raw console key read to a logical key name (pure, terminal-free).

    ``raw`` is the 1- or 2-char sequence :func:`_getch` read: a function / arrow key
    arrives as a ``\\x00`` / ``\\xe0`` prefix byte followed by its scan code (``H`` / ``P``
    → up / down; any other scan code is dropped). A plain key maps ``\\r`` / ``\\x08`` /
    ``\\x1b`` to enter / backspace / escape and passes every other character through.
    """
    if raw[:1] in ("\x00", "\xe0"):  # function / arrow key: raw[1:] holds the scan code
        return {"H": "up", "P": "down"}.get(raw[1:2], "")
    return {"\r": "enter", "\x08": "backspace", "\x1b": "escape"}.get(raw, raw)


def _getch() -> str:  # pragma: no cover - raw single-key read from the real console
    msvcrt = importlib.import_module("msvcrt")
    ch = str(msvcrt.getwch())
    if ch in ("\x00", "\xe0"):  # a function / arrow key → read the scan code too
        ch += str(msvcrt.getwch())
    return decode_key(ch)


def _default_write(
    rows: Sequence[str],
) -> None:  # pragma: no cover - paints the real terminal
    paint(render_frame(rows), stdout())


def run_interactive(
    source: CodexSource,
    *,
    read_key: Callable[[], str] = _getch,
    write: Callable[[Sequence[str]], None] = _default_write,
    clock: Callable[[], float] = time.time,
    cols_fn: Callable[[], int] = lambda: 120,
    initial: ViewState | None = None,
    tracker: StallTracker | None = None,
    mtime_fn: Callable[[str], float | None] = _mtime,
    stale_s: float = 90.0,
) -> ViewState:
    """The keystroke-driven cockpit loop: render → read a key → apply → repeat until quit.

    Blocks on ``read_key`` (a keystroke drives each repaint — no busy poll), so the board is
    responsive without a timer. Returns the final :class:`ViewState` when the user quits.
    """
    state = initial if initial is not None else ViewState()
    tracker = tracker if tracker is not None else StallTracker()
    while True:
        snap = source.poll()
        threads = snap.payload.threads
        now = clock()
        groups = derive_groups(threads)
        marks = stall_marks(tracker, threads, now, stale_s=stale_s, mtime_fn=mtime_fn)
        write(render_view(groups, state, now, cols_fn(), marks=marks))
        state = apply(state, read_key(), groups)
        if state.quit:
            return state


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="Interactive cockpit for the Codex fleet (plain-console drill-down; "
        "--once for a read-only frame that degrades cleanly under Windows Terminal)."
    )
    ap.add_argument("--stream-dir", default=None, help="codex exec --json stream dir")
    ap.add_argument("--sessions-dir", default=None, help="codex rollout sessions dir")
    ap.add_argument("--width", type=int, default=120, help="board width in columns")
    ap.add_argument(
        "--once", action="store_true", help="render a single read-only frame and exit"
    )
    ap.add_argument(
        "--notify",
        action="store_true",
        help="also fire a desktop push on the --once frame",
    )
    return ap


def main(
    argv: Sequence[str] | None = None,
    *,
    source: CodexSource | None = None,
    out: Callable[[str], None] = print,
    clock: Callable[[], float] = time.time,
    interactive: Callable[..., ViewState] = run_interactive,
    notify_fn: Callable[[str], None] = notify,
    supported_fn: Callable[[], bool] = _supported,
) -> int:
    """CLI. ``--once`` (or a non-interactive terminal) renders ONE read-only frame through
    ``out`` and optionally fires a ``--notify`` push; otherwise it hands off to the drill
    loop. The seams are injected so both lanes AND the degradation path are covered.
    """
    args = _build_parser().parse_args(argv)
    src = (
        source
        if source is not None
        else CodexSource(
            stream_dir=args.stream_dir, sessions_dir=args.sessions_dir, clock=clock
        )
    )
    if args.once or not supported_fn():
        snap = src.poll()
        for line in once_frame(snap, args.width):
            out(line)
        if args.notify:
            notify_fn(push_text(snap))
        return 0
    interactive(src, cols_fn=lambda: args.width, clock=clock)
    return 0


if __name__ == "__main__":  # pragma: no cover -- module CLI entrypoint
    raise SystemExit(main())
