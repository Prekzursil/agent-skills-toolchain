"""EXPERIMENTAL ``/mcp`` keystroke macro — a fragile, opt-in escape hatch.

Claude Code has NO robust external live-toggle API (verified: config edits apply
next session; server/proxy-initiated live changes are ignored until restart).
The ONLY external "live" path is to drive the interactive ``/mcp`` TUI by
sending blind keystrokes to a terminal window.  This is inherently brittle:
the list is arrows-only, alphabetical, scrolling, with a per-server submenu, and
terminal text can't be read back reliably.  Treat this as best-effort only.

Design:
- ``plan_navigation`` is PURE and fully tested: it turns a pasted panel order +
  a desired enabled-set into an ordered keystroke plan (arrow counts + submenu
  toggles), navigating relative to a starting cursor row.
- ``run_macro`` orchestrates focus + send via INJECTED callables so it is fully
  testable; the real OS drivers (``pywinauto`` focus, ``pyautogui`` keys) are
  thin, guarded, and never imported at module load.
- Everything is fail-soft: a driver error returns ``(False, reason)`` and never
  raises into the caller / never touches the core config path.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .paste_parse import ParsedServer

# actions a NavStep can carry
DOWN = "down"
UP = "up"
ENTER = "enter"
TOGGLE = "toggle"  # submenu enable/disable selection
BACK = "back"  # leave the submenu (Escape)


@dataclass
class NavStep:
    """One keystroke instruction in a macro plan."""

    action: str
    count: int = 1
    server: str = ""

    def render(self) -> str:
        if self.action in (DOWN, UP):
            return f"{self.action} x{self.count}"
        if self.server:
            return f"{self.action} [{self.server}]"
        return self.action


# ── pure planning ─────────────────────────────────────────────────────────────


def _changes(
    servers: list[ParsedServer], desired_enabled: set[str]
) -> list[tuple[int, str]]:
    """Return (row_index, name) for each server whose state must flip.

    ``desired_enabled`` is matched by exact name.  A server not mentioned in
    ``desired_enabled`` is treated as "should be disabled".
    """
    out: list[tuple[int, str]] = []
    for idx, srv in enumerate(servers):
        want_enabled = srv.name in desired_enabled
        if want_enabled != srv.enabled:
            out.append((idx, srv.name))
    return out


def plan_navigation(
    servers: list[ParsedServer],
    desired_enabled: set[str],
    *,
    start_row: int = 0,
) -> list[NavStep]:
    """Build the keystroke plan to flip the panel to the desired enabled-set.

    ``servers`` MUST be in the exact on-screen (pasted) order — the plan uses
    each row's index for arrow navigation.  Returns an empty plan when nothing
    needs to change.
    """
    steps: list[NavStep] = []
    cursor = start_row
    for target_idx, name in _changes(servers, desired_enabled):
        delta = target_idx - cursor
        if delta > 0:
            steps.append(NavStep(DOWN, delta, name))
        elif delta < 0:
            steps.append(NavStep(UP, -delta, name))
        steps.append(NavStep(ENTER, 1, name))
        steps.append(NavStep(TOGGLE, 1, name))
        steps.append(NavStep(BACK, 1, name))
        cursor = target_idx  # submenu returns to the same row
    return steps


def render_plan(plan: list[NavStep]) -> str:
    """Human-readable, one-step-per-line rendering of a plan."""
    if not plan:
        return "(no changes needed)"
    return "\n".join(f"{i + 1:>3}. {s.render()}" for i, s in enumerate(plan))


# ── orchestration (injected drivers → testable) ───────────────────────────────

# a focuser takes a window title, returns (ok, message)
Focuser = Callable[[str], "tuple[bool, str]"]
# a sender takes one NavStep, performs it, may raise on failure
Sender = Callable[[NavStep], None]


def run_macro(
    plan: list[NavStep],
    window_title: str,
    *,
    focuser: Focuser,
    sender: Sender,
    dry_run: bool = True,
) -> tuple[bool, str]:
    """Focus ``window_title`` then send every step. Fail-soft.

    With ``dry_run`` (the default) nothing is sent — only the plan is validated
    and summarised.  Any driver exception is caught and returned as a failure
    string; this never raises and never touches config.
    """
    if not window_title:
        return False, "no target window specified"
    if not plan:
        return True, "nothing to do (plan is empty)"
    if dry_run:
        return True, f"[dry-run] {len(plan)} step(s) planned for '{window_title}'"

    ok, msg = focuser(window_title)
    if not ok:
        return False, f"could not focus window: {msg}"
    try:
        for step in plan:
            sender(step)
    except Exception as exc:  # noqa: BLE001 - experimental; never crash caller
        return False, f"macro aborted (keystroke driver failed): {exc}"
    return True, f"sent {len(plan)} step(s) to '{window_title}'"


# ── real OS drivers (guarded, never imported at load) ─────────────────────────


def default_focuser(title: str) -> tuple[bool, str]:  # pragma: no cover - OS driving
    """Focus a top-level window by (partial) title via pywinauto."""
    try:
        from pywinauto import Desktop  # type: ignore

        win = Desktop(backend="uia").window(title_re=f".*{title}.*")
        win.set_focus()
        return True, "focused"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


# maps a submenu TOGGLE to a concrete keystroke sequence; overridable by callers
_KEY_FOR_ACTION: dict[str, str] = {
    DOWN: "down",
    UP: "up",
    ENTER: "enter",
    BACK: "esc",
    TOGGLE: "enter",  # submenu default: first item toggles enable/disable
}


def make_pyautogui_sender(
    *, settle: float = 0.05
) -> Sender:  # pragma: no cover - OS driving
    """Build a Sender that presses keys with pyautogui (real terminal driving)."""
    import time

    import pyautogui  # type: ignore

    def _send(step: NavStep) -> None:
        key = _KEY_FOR_ACTION.get(step.action, "enter")
        for _ in range(max(1, step.count)):
            pyautogui.press(key)
            time.sleep(settle)

    return _send
