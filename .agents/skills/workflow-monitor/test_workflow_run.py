#!/usr/bin/env python3
"""Schema-pin fixture test for workflow_run.py.

The Claude Code Workflow MANIFEST (workflows/wf_<id>.json) and its journal.jsonl are INTERNAL,
undocumented shapes (pinned at workflow_run.CC_SCHEMA_VERSION). This test parses a FROZEN real
fixture (a small completed 4-agent run: wf_a04ce988-c26 'codex-chatgpt-signin-feasibility')
committed under ./fixtures/ — NOT the live ~/.claude tree — and asserts the exact WFRun / WFAgent
fields, counts, journal_states, and report_headline. If a future Claude Code release renames or
restructures the manifest/journal, this test FAILS LOUDLY so the monitor is fixed deliberately.

It also asserts FleetPoller's O(changed) contract: an unchanged manifest is NOT re-parsed on the
next poll, and a touched one IS.
"""

from __future__ import annotations

import os

import pytest

import workflow_run as wr

# ── fixture location (mirrors the real fleet layout: <root>/<project>/<session>/workflows/wf_*.json) ──
HERE = os.path.dirname(os.path.abspath(__file__))
FLEET_ROOT = os.path.join(HERE, "fixtures", "projects")
PROJECT = "C--Users-Prekzursil"
SESSION = "d219bc39-7d7f-4290-befd-f1c079161057"
WF_ID = "wf_a04ce988-c26"
MANIFEST = os.path.join(FLEET_ROOT, PROJECT, SESSION, "workflows", WF_ID + ".json")

# ── the frozen expected agent rows (index order), the load-bearing WFAgent fields ──
EXPECTED_AGENTS = [
    {
        "agent_id": "a0175a4851ae12d37",
        "index": 1,
        "label": "official-signin",
        "phase_index": 1,
        "phase_title": "Investigate",
        "model": "claude-opus-4-8[1m]",
        "state": "done",
        "tokens": 107163,
        "tool_calls": 21,
        "last_tool": "WebFetch",
        "attempt": 1,
    },
    {
        "agent_id": "a1e070acdaccdbb5a",
        "index": 2,
        "label": "limits-tos",
        "phase_index": 1,
        "phase_title": "Investigate",
        "model": "claude-opus-4-8[1m]",
        "state": "done",
        "tokens": 103040,
        "tool_calls": 29,
        "last_tool": "WebSearch",
        "attempt": 1,
    },
    {
        "agent_id": "a091094fdf25afb47",
        "index": 3,
        "label": "community-headless",
        "phase_index": 1,
        "phase_title": "Investigate",
        "model": "claude-opus-4-8[1m]",
        "state": "done",
        "tokens": 137587,
        "tool_calls": 19,
        "last_tool": "WebFetch",
        "attempt": 1,
    },
    {
        "agent_id": "a31609916629d126e",
        "index": 4,
        "label": "synthesize",
        "phase_index": 2,
        "phase_title": "Synthesize",
        "model": "claude-opus-4-8[1m]",
        "state": "done",
        "tokens": 80912,
        "tool_calls": 0,
        "last_tool": "",
        "attempt": 1,
    },
]


@pytest.fixture(scope="module")
def run() -> wr.WFRun:
    r = wr.parse_manifest(MANIFEST)
    assert r is not None, "fixture manifest failed to parse — did the schema change?"
    return r


def test_fixture_files_present():
    assert os.path.isfile(MANIFEST), MANIFEST
    r = wr.parse_manifest(MANIFEST)
    assert os.path.isfile(os.path.join(r.subagents_dir(), "journal.jsonl"))


def test_run_scalar_fields(run: wr.WFRun):
    assert run.wf_id == WF_ID
    assert run.name == "codex-chatgpt-signin-feasibility"
    assert run.status == "completed"
    assert run.active is False  # 'completed' is a terminal run status
    assert run.phases == ["Investigate", "Synthesize"]
    assert run.agent_count == 4
    assert run.total_tokens == 428702
    assert run.total_tool_calls == 69
    assert run.duration_ms == 826507
    assert run.started_at == 1783764614013
    assert run.session == SESSION
    assert len(run.agents) == 4


def test_run_counts(run: wr.WFRun):
    assert run.counts == {
        "running": 0,
        "done": 4,
        "error": 0,
        "orphaned": 0,
        "total": 4,
    }


def test_fleet_rollup_single_run(run: wr.WFRun):
    roll = wr.fleet_rollup([run])
    assert roll == {
        "runs": 1,
        "active_runs": 0,
        "running": 0,
        "done": 4,
        "error": 0,
        "orphaned": 0,
        "tokens": 428702,
    }


@pytest.mark.parametrize("i", range(4))
def test_agent_fields(run: wr.WFRun, i: int):
    a = run.agents[i]
    exp = EXPECTED_AGENTS[i]
    for key, want in exp.items():
        assert getattr(a, key) == want, (
            f"agent[{i}].{key}: {getattr(a, key)!r} != {want!r}"
        )
    # derived properties for a completed agent
    assert a.running is False
    assert a.errored is False
    assert a.retrying is False
    # previews are present strings (the drill-down source fields)
    assert isinstance(a.prompt_preview, str) and a.prompt_preview
    assert isinstance(a.result_preview, str) and a.result_preview


def test_agent_idle_ms(run: wr.WFRun):
    a = run.agents[0]
    # last_progress_at is a real epoch-ms; idle is now - last_progress_at
    assert a.last_progress_at > 0
    assert a.idle_ms(a.last_progress_at + 5000) == 5000
    # zero last_progress_at -> zero idle (defensive branch)
    a2 = wr.WFAgent(
        agent_id="x",
        index=0,
        label="x",
        phase_index=0,
        phase_title="",
        model="",
        state="done",
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
    assert a2.idle_ms(1_000_000) == 0.0


def test_journal_states(run: wr.WFRun):
    states = wr.journal_states(run.subagents_dir())
    assert states == {
        "a0175a4851ae12d37": "result",
        "a1e070acdaccdbb5a": "result",
        "a091094fdf25afb47": "result",
        "a31609916629d126e": "result",
    }


def test_report_headline(run: wr.WFRun):
    a0 = run.agents[0]
    out = wr.agent_output(
        os.path.join(run.subagents_dir(), a0.agent_id + ".jsonl"),
        run.subagents_dir(),
        a0.agent_id,
    )
    assert out  # journal `result` recovered the clean output
    assert wr.report_headline(out) == "HEADLINE ANSWER (yes/no)"
    # NOTE: report_headline's pure-branch unit tests moved to
    # tools/monitorcore/tests/test_timeline.py (the symbol now lives in
    # monitorcore.timeline; `wr.report_headline` resolves via the re-export shim).


# ── FleetPoller O(changed) contract ──
def test_fleet_poller_discovers_fixture():
    runs = wr.FleetPoller(FLEET_ROOT).poll()
    ids = [r.wf_id for r in runs]
    assert WF_ID in ids
    assert len(runs) == 1  # exactly one manifest under the fixture root


def test_fleet_poller_reparses_only_changed(monkeypatch):
    calls: list[str] = []
    real = wr.parse_manifest

    def counting_parse(path, mtime=None):
        calls.append(path)
        return real(path, mtime)

    monkeypatch.setattr(wr, "parse_manifest", counting_parse)

    poller = wr.FleetPoller(FLEET_ROOT)

    # 1st poll: the one fixture manifest is parsed once
    poller.poll()
    assert len(calls) == 1

    # 2nd poll: nothing changed → NOT re-parsed (O(changed), not O(all))
    poller.poll()
    assert len(calls) == 1, "unchanged manifest must not be re-parsed"

    # touch it (bump mtime) → re-parsed exactly once more
    st = os.stat(MANIFEST)
    os.utime(MANIFEST, (st.st_atime, st.st_mtime + 10))
    try:
        poller.poll()
        assert len(calls) == 2, "a changed manifest must be re-parsed"
        poller.poll()
        assert len(calls) == 2, "still-unchanged manifest must not be re-parsed again"
    finally:
        os.utime(MANIFEST, (st.st_atime, st.st_mtime))  # restore original mtime
