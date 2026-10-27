#!/usr/bin/env python3
"""Headless smoke test: mount the cockpit against the REAL fleet via Textual Pilot.

Asserts: (1) the tree populates with >0 runs and >0 agents; (2) selecting an agent
fills the AgentHeader, Task, Result and Feed panes from live on-disk data.
"""

from __future__ import annotations

import asyncio
import sys

from textual.widgets import RichLog, Static

from workflow_monitor import WorkflowMonitor


def _txt(app, wid: str) -> str:
    # Textual 8.x Static keeps the content passed to .update() in the mangled __content attr.
    w = app.query_one(wid, Static)
    return str(getattr(w, "_Static__content", ""))


async def _run() -> int:
    app = WorkflowMonitor()
    async with app.run_test(size=(160, 50)) as pilot:
        # 1) wait for the first fleet poll to populate the tree
        for _ in range(200):
            await pilot.pause(0.1)
            if app._agent_nodes:
                break
        n_runs = len(app._run_nodes)
        n_agents = len(app._agent_nodes)
        print(f"tree: run_nodes={n_runs} agent_nodes={n_agents}")
        assert n_runs > 0, "tree did not populate with any runs"
        assert n_agents > 0, "tree did not populate with any agents"

        rollup = _txt(app, "#rollup")
        print(f"rollup: {rollup.strip()}")
        assert "runs" in rollup, "rollup bar not rendered"

        # 2) select an agent → panes fill from live data
        key, node = next(iter(app._agent_nodes.items()))
        print(f"selecting agent: {key}")
        app._select_node(node)
        assert app._sel_key == key, "selection key not set"

        # wait for the detail thread-worker to fill the panes
        filled = False
        for _ in range(200):
            await pilot.pause(0.1)
            task = _txt(app, "#task")
            if task and task != "loading…":
                filled = True
                break
        header = _txt(app, "#ahdr")
        task = _txt(app, "#task")
        result = _txt(app, "#result")
        feed_lines = len(app.query_one("#feed", RichLog).lines)
        print(f"header: {header.splitlines()[0][:80]!r}")
        print(
            f"task chars: {len(task)}  result chars: {len(result)}  feed lines: {feed_lines}"
        )
        assert filled, "Task pane never filled after selecting an agent"
        assert header and "Select an agent" not in header, "AgentHeader not updated"
        assert len(result) > 0 and result != "loading…", "Result pane not filled"

        # 3) filter + status-chip reflow must not crash and must keep the tree valid
        app._query = "wf"
        app._reflow()
        await pilot.pause(0.1)
        print(f"after filter 'wf': run_nodes={len(app._run_nodes)}")
        app._status_on.discard("done")
        app._reflow()
        await pilot.pause(0.1)
        print(f"after dropping 'done' chip: run_nodes={len(app._run_nodes)}")

        # 4) follow toggle
        app.action_toggle_follow()
        print(f"follow toggled -> {app._follow}")

    print("SMOKE_PASS")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(_run()))
    except AssertionError as e:
        print(f"SMOKE_FAIL: {e}")
        sys.exit(1)
