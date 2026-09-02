"""Tests for core/live_macro.py — the EXPERIMENTAL /mcp keystroke macro.

Only the pure planning + injected-driver orchestration is tested; the real OS
drivers (pywinauto/pyautogui) are pragma-excluded and never touched here.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import live_macro as lm  # noqa: E402
from core.paste_parse import ParsedServer  # noqa: E402


def _srv(name: str, state: str) -> ParsedServer:
    return ParsedServer(name=name, state=state)


# ── NavStep.render ────────────────────────────────────────────────────────────


class TestNavStepRender:
    def test_arrow_shows_count(self):
        assert lm.NavStep(lm.DOWN, 3, "x").render() == "down x3"
        assert lm.NavStep(lm.UP, 2, "x").render() == "up x2"

    def test_action_with_server(self):
        assert lm.NavStep(lm.ENTER, 1, "tavily").render() == "enter [tavily]"

    def test_action_without_server(self):
        assert lm.NavStep(lm.BACK).render() == "back"


# ── plan_navigation ───────────────────────────────────────────────────────────


class TestPlanNavigation:
    def test_no_changes_empty_plan(self):
        servers = [_srv("a", "connected"), _srv("b", "disabled")]
        # a already enabled, b already disabled -> nothing to do
        plan = lm.plan_navigation(servers, {"a"})
        assert plan == []

    def test_enable_and_disable_flips(self):
        servers = [
            _srv("a", "connected"),
            _srv("b", "disabled"),
            _srv("c", "connected"),
        ]
        # want {a, b} enabled -> b flips on (idx1), c flips off (idx2)
        plan = lm.plan_navigation(servers, {"a", "b"})
        actions = [(s.action, s.count, s.server) for s in plan]
        assert actions == [
            (lm.DOWN, 1, "b"),
            (lm.ENTER, 1, "b"),
            (lm.TOGGLE, 1, "b"),
            (lm.BACK, 1, "b"),
            (lm.DOWN, 1, "c"),
            (lm.ENTER, 1, "c"),
            (lm.TOGGLE, 1, "c"),
            (lm.BACK, 1, "c"),
        ]

    def test_zero_delta_has_no_arrow_step(self):
        servers = [_srv("a", "disabled")]
        plan = lm.plan_navigation(servers, {"a"})  # flip idx0 from cursor 0
        assert plan[0].action == lm.ENTER  # no leading arrow

    def test_up_navigation_when_cursor_ahead(self):
        servers = [_srv("a", "disabled"), _srv("b", "connected")]
        # start cursor at row 5 -> first target (idx0) needs UP x5
        plan = lm.plan_navigation(servers, {"a", "b"}, start_row=5)
        assert plan[0].action == lm.UP
        assert plan[0].count == 5


# ── render_plan ───────────────────────────────────────────────────────────────


class TestRenderPlan:
    def test_empty(self):
        assert lm.render_plan([]) == "(no changes needed)"

    def test_numbered(self):
        plan = [lm.NavStep(lm.DOWN, 1, "a"), lm.NavStep(lm.ENTER, 1, "a")]
        rendered = lm.render_plan(plan)
        assert "1." in rendered
        assert "down x1" in rendered


# ── run_macro (injected drivers) ──────────────────────────────────────────────


def _ok_focuser(title: str) -> tuple[bool, str]:
    return True, "focused"


def _fail_focuser(title: str) -> tuple[bool, str]:
    return False, "not found"


class _RecordingSender:
    def __init__(self) -> None:
        self.steps: list[lm.NavStep] = []

    def __call__(self, step: lm.NavStep) -> None:
        self.steps.append(step)


def _raising_sender(step: lm.NavStep) -> None:
    raise RuntimeError("keystroke boom")


class TestRunMacro:
    def _plan(self) -> list[lm.NavStep]:
        return [lm.NavStep(lm.ENTER, 1, "a")]

    def test_no_window_fails(self):
        ok, msg = lm.run_macro(
            self._plan(), "", focuser=_ok_focuser, sender=_RecordingSender()
        )
        assert ok is False
        assert "window" in msg

    def test_empty_plan_ok(self):
        ok, msg = lm.run_macro(
            [], "win", focuser=_ok_focuser, sender=_RecordingSender()
        )
        assert ok is True
        assert "nothing to do" in msg

    def test_dry_run_sends_nothing(self):
        sender = _RecordingSender()
        ok, msg = lm.run_macro(
            self._plan(), "win", focuser=_ok_focuser, sender=sender, dry_run=True
        )
        assert ok is True
        assert "dry-run" in msg
        assert sender.steps == []

    def test_focus_failure(self):
        ok, msg = lm.run_macro(
            self._plan(),
            "win",
            focuser=_fail_focuser,
            sender=_RecordingSender(),
            dry_run=False,
        )
        assert ok is False
        assert "focus" in msg

    def test_sender_exception_is_soft(self):
        ok, msg = lm.run_macro(
            self._plan(),
            "win",
            focuser=_ok_focuser,
            sender=_raising_sender,
            dry_run=False,
        )
        assert ok is False
        assert "aborted" in msg

    def test_success_sends_all_steps(self):
        sender = _RecordingSender()
        plan = [lm.NavStep(lm.DOWN, 1, "a"), lm.NavStep(lm.ENTER, 1, "a")]
        ok, msg = lm.run_macro(
            plan, "win", focuser=_ok_focuser, sender=sender, dry_run=False
        )
        assert ok is True
        assert len(sender.steps) == 2
        assert "sent 2" in msg
