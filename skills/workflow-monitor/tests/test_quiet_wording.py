"""Focused regression tests for honest quiet-agent rendering and triage."""

from __future__ import annotations

import workflow_monitor as wm
import workflow_run as wr
from monitorcore import agent_state


def _agent(**over):
    """Build a WFAgent with the given overrides on top of a benign baseline."""
    base = dict(
        agent_id="x",
        index=0,
        label="x",
        phase_index=0,
        phase_title="",
        model="",
        state="progress",
        tokens=0,
        tool_calls=0,
        duration_ms=0,
        last_tool="",
        last_summary="",
        prompt_preview="",
        result_preview="",
        attempt=1,
        started_at=0,
        last_progress_at=0,
    )
    base.update(over)
    return wr.WFAgent(**base)


def _run(agent: wr.WFAgent, *, wf_id: str) -> wr.WFRun:
    return wr.WFRun(
        wf_id=wf_id,
        name=wf_id,
        status="running",
        phases=[],
        agent_count=1,
        total_tokens=0,
        total_tool_calls=0,
        duration_ms=0,
        started_at=0,
        manifest_path="",
        session="",
        mtime=0.0,
        agents=[agent],
    )


def test_quiet_threshold_comes_from_monitorcore():
    assert wm.QUIET_MS == agent_state.STALL * 1000
    assert wm.QUIET_MS > 90_000


def test_ten_minute_longrun_renders_measured_quiet_fact():
    now = 1_000_000.0
    agent = _agent(last_progress_at=now - wm.QUIET_MS - 1)
    plain = wm._agent_line(agent, now).plain
    assert "quiet 10m 0s" in plain
    assert "STALL" not in plain


def test_old_ninety_second_false_positive_band_stays_unmarked():
    now = 1_000_000.0
    # Direct regression for the measured 12.10% of tool calls above the old 90s cutoff.
    agent = _agent(last_progress_at=now - 100_000)
    assert "quiet" not in wm._agent_line(agent, now).plain


def test_quiet_run_is_not_rendered_as_red_error():
    now = 1_000_000.0
    quiet = _run(_agent(last_progress_at=now - wm.QUIET_MS - 1), wf_id="quiet")
    errored = _run(_agent(state="error"), wf_id="error")

    quiet_label = wm._run_label(quiet, now)
    error_label = wm._run_label(errored, now)
    assert quiet_label.plain.startswith("~ ")
    assert quiet_label.spans[0].style != "bold red"
    assert error_label.plain.startswith("! ")
    assert error_label.spans[0].style == "bold red"


def test_error_sorts_ahead_of_quiet_run_and_agent():
    now = 1_000_000.0
    quiet_agent = _agent(last_progress_at=now - wm.QUIET_MS - 1)
    error_agent = _agent(state="error")
    quiet = _run(quiet_agent, wf_id="quiet")
    errored = _run(error_agent, wf_id="error")

    app = wm.WorkflowMonitor()
    app._runs_all = [quiet, errored]
    app._query = ""
    app._status_on = set(wm.STATUSES)
    picked, _ = app._display_runs(now)
    assert [run.wf_id for run, _ in picked] == ["error", "quiet"]
    assert wm._agent_priority(error_agent, now) < wm._agent_priority(quiet_agent, now)


def test_run_leaf_budget_has_no_cross_phase_triage_inversion():
    now = 1_000_000.0
    done = [
        _agent(agent_id=f"done-{i}", index=i, state="done", phase_title="early")
        for i in range(wm.MAX_AGENTS_PER_RUN)
    ]
    lost = [
        _agent(
            agent_id=f"lost-{i}",
            index=wm.MAX_AGENTS_PER_RUN + i,
            state="lost",
            phase_index=-1,
            phase_title=wr.JOURNAL_ONLY_PHASE,
        )
        for i in range(3)
    ]
    agents = done + lost

    survivors = wm._triage_budget(agents, now)
    kept = [agent for agent in agents if id(agent) in survivors]
    dropped = [agent for agent in agents if id(agent) not in survivors]

    assert any(agent.state == "lost" for agent in kept)
    assert max(wm._agent_priority(agent, now) for agent in kept) <= min(
        wm._agent_priority(agent, now) for agent in dropped
    )
