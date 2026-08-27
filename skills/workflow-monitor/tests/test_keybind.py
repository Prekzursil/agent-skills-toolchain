"""Cockpit ``e`` export keybind — Textual Pilot integration (OUTSIDE the 100% coverage lane).

Drives the real :class:`WorkflowMonitor` against the frozen ``wf_export00-fixture`` fleet and
exercises the keybind wiring end-to-end: the ``e`` binding runs ``action_export`` which reads
``tree.cursor_node.data``, maps run/agent selections to a scope, and dispatches an off-thread
``@work(group="export")`` worker that lazy-imports ``wfmon_export.cli.run_export``.

The worker's ``run_export`` dependency is stubbed via a fake ``wfmon_export.cli`` module injected
into ``sys.modules`` so this test verifies *the keybind's* contract (scope, agents, out dir,
``projects=self.poller.projects``, success/failure toasts, read-only, no deadlock) in isolation —
the real render/collect integration is covered by ``tests/test_cli.py``. Skips when textual is
absent (the cockpit itself is optional at export time).
"""

from __future__ import annotations

import os
import sys
import types

import pytest

pytest.importorskip("textual")

import workflow_monitor as wm  # noqa: E402

_SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE_ROOT = os.path.realpath(
    os.path.join(_SKILL_ROOT, "fixtures", "export", "projects")
)
WF_ID = "wf_export00-fixture"


# ── test doubles ─────────────────────────────────────────────────────────────
def _install_fake_cli(monkeypatch, recorder, *, boom: bool = False):
    """Inject a fake ``wfmon_export.cli`` whose ``run_export`` records its kwargs.

    When ``boom`` it raises (to assert the worker's fail-closed toast). Otherwise it writes a
    real file into ``out`` and returns its path, so a recorded call implies the file exists.
    """
    mod = types.ModuleType("wfmon_export.cli")

    def run_export(
        wf_id,
        *,
        scope="run",
        agents=None,
        fmt="md",
        pdf_engine=None,
        tools="full",
        thinking=True,
        redact=True,
        out=None,
        projects=None,
    ):
        if boom:
            raise RuntimeError("engine exploded")
        os.makedirs(out, exist_ok=True)
        path = os.path.join(out, f"{wf_id}.md")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("# export\n")
        recorder["calls"].append(
            {
                "wf_id": wf_id,
                "scope": scope,
                "agents": agents,
                "fmt": fmt,
                "tools": tools,
                "thinking": thinking,
                "redact": redact,
                "out": out,
                "projects": projects,
                "path": path,
            }
        )
        return path

    mod.run_export = run_export
    monkeypatch.setitem(sys.modules, "wfmon_export.cli", mod)


def _install_notify_spy(monkeypatch, app, toasts):
    def fake_notify(message, *, title="", severity="information", timeout=None, **_):
        toasts.append({"message": message, "severity": severity})

    monkeypatch.setattr(app, "notify", fake_notify)


async def _wait_until(pilot, cond, *, tries: int = 300, delay: float = 0.02) -> bool:
    for _ in range(tries):
        if cond():
            return True
        await pilot.pause(delay)
    return False


async def _prime_fleet(pilot, app) -> None:
    """Point the poller at the fixture fleet and force polls until the run node is built."""
    app.poller.projects = FIXTURE_ROOT
    built = False
    for _ in range(300):
        if WF_ID in app._run_nodes:
            built = True
            break
        app.action_force_poll()
        await pilot.pause(0.02)
    assert built, "poll worker never built the fixture run node"


# ── tests ────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_export_run_node_via_e_key(monkeypatch, tmp_path):
    """Cursor on a run node + press ``e`` → scope=run export lands a file; success toast."""
    recorder = {"calls": []}
    _install_fake_cli(monkeypatch, recorder)
    monkeypatch.setattr(wm.tempfile, "gettempdir", lambda: str(tmp_path))

    app = wm.WorkflowMonitor()
    async with app.run_test() as pilot:
        toasts: list[dict] = []
        _install_notify_spy(monkeypatch, app, toasts)
        await _prime_fleet(pilot, app)

        tree = app.query_one("#tree", wm.Tree)
        tree.focus()
        await pilot.pause()
        tree.move_cursor(app._run_nodes[WF_ID])
        await pilot.pause()
        assert tree.cursor_node is app._run_nodes[WF_ID]

        await pilot.press("e")
        assert await _wait_until(pilot, lambda: recorder["calls"]), (
            "export worker never called run_export"
        )

        (call,) = recorder["calls"]
        assert call["wf_id"] == WF_ID
        assert call["scope"] == "run"
        assert call["agents"] is None
        assert call["projects"] == FIXTURE_ROOT
        # keybind defaults per the plan
        assert (call["fmt"], call["tools"], call["thinking"], call["redact"]) == (
            "md",
            "full",
            True,
            True,
        )
        # default out dir = <tempdir>/wfmon-exports (tempdir monkeypatched into tmp_path)
        assert os.path.realpath(call["out"]) == os.path.realpath(
            os.path.join(str(tmp_path), "wfmon-exports")
        )
        assert os.path.isfile(call["path"])

        assert await _wait_until(
            pilot, lambda: any("exported" in t["message"] for t in toasts)
        ), "no success toast after export"

        # UI is not wedged: the poll loop still cycles and is not stuck mid-flight.
        app.action_force_poll()
        assert await _wait_until(pilot, lambda: app._polling is False)
        assert WF_ID in app._run_nodes


@pytest.mark.asyncio
async def test_export_agent_node_scopes_by_label(monkeypatch, tmp_path):
    """Cursor on an agent node → scope=agent pre-filled with that agent's label."""
    recorder = {"calls": []}
    _install_fake_cli(monkeypatch, recorder)
    monkeypatch.setattr(wm.tempfile, "gettempdir", lambda: str(tmp_path))

    app = wm.WorkflowMonitor()
    async with app.run_test() as pilot:
        toasts: list[dict] = []
        _install_notify_spy(monkeypatch, app, toasts)
        await _prime_fleet(pilot, app)

        akey = f"{WF_ID}/agent-kitchensink"
        assert await _wait_until(pilot, lambda: akey in app._agent_nodes)
        tree = app.query_one("#tree", wm.Tree)
        tree.move_cursor(app._agent_nodes[akey])
        await pilot.pause()

        # drive the action directly (deterministic; the key path is covered above)
        app.action_export()
        assert await _wait_until(pilot, lambda: recorder["calls"])

        (call,) = recorder["calls"]
        assert call["wf_id"] == WF_ID
        assert call["scope"] == "agent"
        assert call["agents"] == ["kitchensink"]


@pytest.mark.asyncio
async def test_export_no_selection_warns(monkeypatch, tmp_path):
    """Nothing selectable (root node, data=None) → warning toast, run_export NOT called."""
    recorder = {"calls": []}
    _install_fake_cli(monkeypatch, recorder)
    monkeypatch.setattr(wm.tempfile, "gettempdir", lambda: str(tmp_path))

    app = wm.WorkflowMonitor()
    async with app.run_test() as pilot:
        toasts: list[dict] = []
        _install_notify_spy(monkeypatch, app, toasts)
        await _prime_fleet(pilot, app)

        tree = app.query_one("#tree", wm.Tree)
        tree.move_cursor(tree.root)  # data is None → not selectable
        await pilot.pause()

        app.action_export()
        await pilot.pause()
        assert recorder["calls"] == []
        assert any(t["severity"] == "warning" for t in toasts)


@pytest.mark.asyncio
async def test_export_worker_failure_toasts_not_crash(monkeypatch, tmp_path):
    """A failing run_export (e.g. missing optional dep) degrades to a warning toast, no crash."""
    recorder = {"calls": []}
    _install_fake_cli(monkeypatch, recorder, boom=True)
    monkeypatch.setattr(wm.tempfile, "gettempdir", lambda: str(tmp_path))

    app = wm.WorkflowMonitor()
    async with app.run_test() as pilot:
        toasts: list[dict] = []
        _install_notify_spy(monkeypatch, app, toasts)
        await _prime_fleet(pilot, app)

        tree = app.query_one("#tree", wm.Tree)
        tree.move_cursor(app._run_nodes[WF_ID])
        await pilot.pause()

        app.action_export()
        assert await _wait_until(
            pilot, lambda: any("failed" in t["message"] for t in toasts)
        ), "no failure toast when run_export raised"
        assert app.is_running  # cockpit survived the worker exception
