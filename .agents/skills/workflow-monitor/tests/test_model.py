#!/usr/bin/env python3
"""``wfmon_export.model`` aggregator tests: ``collect_run`` + ``_state_bucket`` against the
frozen ``wf_export00-fixture`` (2 phases / 3 agents, states done / error / running).

All fixture-reading tests point at the ISOLATED export fixture root ``fixtures/export/projects``
(never the live ``~/.claude`` tree, never the schema-lock ``fixtures/projects`` root — so
``test_workflow_run.py``'s single-manifest invariant stays true). ``model.py`` is the ONLY
filesystem reader in the export path; renderers are pure of the returned ``ExportModel``.
"""

from __future__ import annotations

import json
import os
import pathlib

import pytest

import workflow_run as wr
from wfmon_export import model as m

# ── isolated export fixture root (mirrors test_timeline.py's EXPORT_PROJECTS) ──
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPORT_PROJECTS = os.path.join(HERE, "fixtures", "export", "projects")
PROJECT = "C--Users-Prekzursil"
SESSION = "d219bc39-7d7f-4290-befd-f1c079161057"
WF_ID = "wf_export00-fixture"


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


# ───────────────────────── _state_bucket (pure) ─────────────────────────
def test_state_bucket_error_from_manifest():
    # journal_states cannot express error; errored comes from the manifest state
    a = _agent(state="error")
    assert a.errored is True
    assert m._state_bucket(a, "started") == "error"


def test_state_bucket_done_from_journal_result():
    # not errored + journal 'result' -> done even if manifest state is not 'done'
    a = _agent(state="progress")
    assert m._state_bucket(a, "result") == "done"


def test_state_bucket_done_from_manifest_state():
    # not errored + journal not 'result' + manifest state 'done' -> done
    a = _agent(state="done")
    assert m._state_bucket(a, "started") == "done"
    assert m._state_bucket(a, None) == "done"


def test_state_bucket_running():
    # not errored + not done + running property true -> running
    a = _agent(state="progress")
    assert a.running is True
    assert m._state_bucket(a, "started") == "running"


def test_state_bucket_idle():
    # not errored + not done + not running -> idle (a non-running, non-terminal state)
    a = _agent(state="cancelled")
    assert a.running is False
    assert a.errored is False
    assert m._state_bucket(a, None) == "idle"


# ───────────────────────── collect_run: shape ─────────────────────────
@pytest.fixture(scope="module")
def run_model() -> m.ExportModel:
    return m.collect_run(WF_ID, projects=EXPORT_PROJECTS)


def test_collect_run_returns_export_model(run_model):
    assert isinstance(run_model, m.ExportModel)
    assert run_model.wf_id == WF_ID
    assert run_model.name == "wfmon-export-fixture"
    assert run_model.status == "running"
    assert run_model.session == SESSION
    assert run_model.manifest_path.endswith(WF_ID + ".json")


def test_collect_run_active_flag_non_terminal(run_model):
    # 'running' is a non-terminal status -> the 'run still active — snapshot' banner fires
    assert run_model.status == "running"
    assert run_model.active is True


def test_collect_run_schema_version_pinned(run_model):
    assert run_model.schema_version == wr.CC_SCHEMA_VERSION == "2.1.207"


def test_collect_run_two_phases_three_agents(run_model):
    assert [p.title for p in run_model.phases] == ["Investigate", "Synthesize"]
    assert [p.index for p in run_model.phases] == [1, 2]
    # manifest index order within a phase
    assert [a.label for a in run_model.phases[0].agents] == [
        "kitchensink",
        "secretcheck",
    ]
    assert [a.label for a in run_model.phases[1].agents] == ["taskorder"]
    total = sum(len(p.agents) for p in run_model.phases)
    assert total == 3


def _agents_by_label(model: m.ExportModel) -> dict:
    return {a.label: a for p in model.phases for a in p.agents}


def test_collect_run_state_buckets(run_model):
    by = _agents_by_label(run_model)
    assert by["kitchensink"].state == "done"  # journal result + manifest 'done'
    assert by["secretcheck"].state == "error"  # manifest 'error'
    assert by["taskorder"].state == "running"  # manifest 'progress'


def test_collect_run_agent_scalar_fields(run_model):
    ks = _agents_by_label(run_model)["kitchensink"]
    assert ks.agent_id == "agent-kitchensink"
    assert ks.index == 1
    assert ks.phase_index == 1
    assert ks.phase_title == "Investigate"
    assert ks.model == "claude-opus-4-8[1m]"
    assert ks.tokens == 1000
    assert ks.tool_calls == 4
    assert ks.attempt == 1
    # jsonl path is built as agent-<agentId>.jsonl (agentId already carries 'agent-')
    assert ks.jsonl_path == os.path.join(
        EXPORT_PROJECTS,
        PROJECT,
        SESSION,
        "subagents",
        "workflows",
        WF_ID,
        "agent-kitchensink.jsonl",
    )
    assert os.path.isfile(ks.jsonl_path)


def test_collect_run_retrying_agent_attempt(run_model):
    sc = _agents_by_label(run_model)["secretcheck"]
    assert sc.attempt == 2  # attempt 2 -> retrying in the manifest model


def test_collect_run_task_output_headline_timeline(run_model):
    by = _agents_by_label(run_model)
    ks = by["kitchensink"]
    # agent_task = FIRST user text (spawn prompt), NOT the largest message
    assert ks.task == "Do the kitchen-sink task."
    # agent_output = journal `result` for kitchensink; headline = first markdown heading
    assert ks.output == (
        "# Kitchensink Report\nAll transcript block kinds are covered by this fixture."
    )
    assert ks.headline == "Kitchensink Report"
    assert len(ks.timeline) == 13
    assert all(isinstance(e, wr.TimelineEvent) for e in ks.timeline)

    # taskorder: no journal result -> falls back to the last assistant message
    to = by["taskorder"]
    assert to.task == "short task"
    assert to.output == "working on the ordered task"


# ───────────────────────── collect_run: rollup ─────────────────────────
def test_collect_run_rollup_scoped(run_model):
    assert run_model.rollup == {
        "running": 1,
        "done": 1,
        "error": 1,
        "idle": 0,
        "total": 3,
        "tokens": 1750,
    }


# ───────────────────────── collect_run: provenance ─────────────────────────
def test_collect_run_provenance_keys(run_model):
    prov = run_model.provenance
    assert set(prov) == {
        "wf_id",
        "name",
        "session",
        "scope",
        "redaction_mode",
        "generated_at",
        "schema_version",
    }
    assert prov["wf_id"] == WF_ID
    assert prov["name"] == "wfmon-export-fixture"
    assert prov["session"] == SESSION
    assert prov["scope"] == "run"
    assert prov["redaction_mode"] == "strict"
    assert prov["schema_version"] == wr.CC_SCHEMA_VERSION
    assert isinstance(prov["generated_at"], str) and prov["generated_at"]
    # generated_at is echoed onto the model too
    assert run_model.generated_at == prov["generated_at"]


def test_collect_run_default_scope_and_redaction(run_model):
    assert run_model.scope == "run"
    assert run_model.scope_agents == []
    assert run_model.redaction_mode == "strict"


# ───────────────────────── collect_run: scoping ─────────────────────────
def test_scope_agent_single_label():
    model = m.collect_run(
        WF_ID, projects=EXPORT_PROJECTS, scope="agent", agents=["kitchensink"]
    )
    labels = [a.label for p in model.phases for a in p.agents]
    assert labels == ["kitchensink"]
    assert model.scope == "agent"
    assert model.scope_agents == ["kitchensink"]
    assert model.rollup == {
        "running": 0,
        "done": 1,
        "error": 0,
        "idle": 0,
        "total": 1,
        "tokens": 1000,
    }
    # only the phase containing the scoped agent survives
    assert [p.title for p in model.phases] == ["Investigate"]


def test_scope_agent_case_insensitive():
    model = m.collect_run(
        WF_ID, projects=EXPORT_PROJECTS, scope="agent", agents=["KITCHENSINK"]
    )
    assert [a.label for p in model.phases for a in p.agents] == ["kitchensink"]


def test_scope_subset_multiple_labels():
    model = m.collect_run(
        WF_ID,
        projects=EXPORT_PROJECTS,
        scope="subset",
        agents=["kitchensink", "taskorder"],
    )
    labels = [a.label for p in model.phases for a in p.agents]
    assert labels == ["kitchensink", "taskorder"]
    # both phases represented; secretcheck excluded
    assert [p.title for p in model.phases] == ["Investigate", "Synthesize"]
    assert model.rollup == {
        "running": 1,
        "done": 1,
        "error": 0,
        "idle": 0,
        "total": 2,
        "tokens": 1250,
    }
    assert model.scope_agents == ["kitchensink", "taskorder"]


def test_scope_unknown_label_raises_value_error():
    with pytest.raises(ValueError) as ei:
        m.collect_run(WF_ID, projects=EXPORT_PROJECTS, scope="agent", agents=["nope"])
    msg = str(ei.value)
    assert "nope" in msg
    # the available labels are listed to guide the caller
    for label in ("kitchensink", "secretcheck", "taskorder"):
        assert label in msg


def test_scope_subset_requires_agents():
    with pytest.raises(ValueError):
        m.collect_run(WF_ID, projects=EXPORT_PROJECTS, scope="subset", agents=None)
    with pytest.raises(ValueError):
        m.collect_run(WF_ID, projects=EXPORT_PROJECTS, scope="subset", agents=[])


# ───────────────────────── collect_run: lookup failures ─────────────────────────
def test_unknown_wf_id_raises_lookup_error_lists_all():
    with pytest.raises(LookupError) as ei:
        m.collect_run("wf_totally-absent-zzz", projects=EXPORT_PROJECTS)
    # nothing is close -> the message falls back to listing the known ids
    assert WF_ID in str(ei.value)


def test_unknown_wf_id_lookup_error_near_match():
    # a near-miss (single-char typo) surfaces the close match
    with pytest.raises(LookupError) as ei:
        m.collect_run("wf_export00-fixtur", projects=EXPORT_PROJECTS)
    assert WF_ID in str(ei.value)


def test_collect_run_skips_unreadable_manifest(tmp_path):
    # a garbage manifest parses to None and is skipped; the valid one is still found
    root = tmp_path / "projects"
    wf_dir = root / "proj" / "sess" / "workflows"
    wf_dir.mkdir(parents=True)
    (wf_dir / "wf_bad.json").write_text("{ this is not json", encoding="utf-8")
    good = {
        "runId": "wf_good",
        "workflowName": "good-run",
        "status": "completed",
        "phases": [{"title": "Only"}],
        "workflowProgress": [
            {
                "type": "workflow_agent",
                "index": 1,
                "label": "solo",
                "phaseIndex": 1,
                "phaseTitle": "Only",
                "agentId": "agent-solo",
                "state": "done",
                "tokens": 42,
            }
        ],
    }
    (wf_dir / "wf_good.json").write_text(json.dumps(good), encoding="utf-8")

    model = m.collect_run("wf_good", projects=str(root))
    assert model.wf_id == "wf_good"
    assert model.active is False  # 'completed' is terminal
    assert [a.label for p in model.phases for a in p.agents] == ["solo"]
    assert model.rollup["tokens"] == 42


# ───────────────────────── purity / no-workflow_monitor invariant ─────────────────────────
def test_model_does_not_import_workflow_monitor():
    # precise: no IMPORT of workflow_monitor (docstrings may name it; the state bucket is local)
    import ast

    tree = ast.parse(pathlib.Path(m.__file__).read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    assert not any(name.split(".")[0] == "workflow_monitor" for name in imported)


def test_collect_run_is_fully_materialized(run_model):
    # no open file handles / lazy readers survive into the model: every field is plain data,
    # so renderers can be pure functions of the model (fs touched only here).
    for phase in run_model.phases:
        assert isinstance(phase.agents, list)
        for a in phase.agents:
            assert isinstance(a.task, str)
            assert isinstance(a.output, str)
            assert isinstance(a.headline, str)
            assert isinstance(a.jsonl_path, str)
            assert isinstance(a.timeline, list)
    # deep-copy proves there are no un-pickleable live handles embedded
    import copy

    clone = copy.deepcopy(run_model)
    assert clone.wf_id == run_model.wf_id
    assert clone.rollup == run_model.rollup


# ───────────────────────── package re-export ─────────────────────────
def test_package_reexports_collect_run():
    import wfmon_export

    assert wfmon_export.collect_run is m.collect_run
    assert set({"AgentExport", "ExportModel", "PhaseExport", "collect_run"}) <= set(
        wfmon_export.__all__
    )


def test_package_getattr_unknown_raises():
    import wfmon_export

    with pytest.raises(AttributeError):
        wfmon_export.this_symbol_does_not_exist
