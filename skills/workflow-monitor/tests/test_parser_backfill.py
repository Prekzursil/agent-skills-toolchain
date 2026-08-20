#!/usr/bin/env python3
"""Legacy-parser backfill: drives the reused ``workflow_run.py`` helpers to 100% branch coverage.

PR-A reuses the small, pure ``workflow_run`` parser inside ``collect_run``, so the whole module is
gated at 100% (like the repo's other python packages). ``test_workflow_run.py`` pins the happy path
against the frozen real run; this file adds the DEFENSIVE branches (OSError / malformed JSON / dict
vs str results / gone-manifest removal / unparseable manifests / state buckets) using the isolated
``wf_export00-fixture`` and purpose-built tmp inputs.
"""

from __future__ import annotations

import json
import os

import workflow_run as wr

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPORT_PROJECTS = os.path.join(HERE, "fixtures", "export", "projects")
PROJECT = "C--Users-Prekzursil"
SESSION = "d219bc39-7d7f-4290-befd-f1c079161057"
WF_ID = "wf_export00-fixture"
MANIFEST = os.path.join(EXPORT_PROJECTS, PROJECT, SESSION, "workflows", WF_ID + ".json")
WF_DIR = os.path.join(
    EXPORT_PROJECTS, PROJECT, SESSION, "subagents", "workflows", WF_ID
)

# the schema-lock root (one completed run) — used to exercise the not-active poller arc
LOCK_ROOT = os.path.join(HERE, "fixtures", "projects")


# ───────────────────────── tiny coercion helpers ─────────────────────────
def test__i_int_float_and_default():
    assert wr._i({"a": 5}, "a") == 5
    assert wr._i({"a": 5.9}, "a") == 5
    assert wr._i({"a": "x"}, "a") == 0
    assert wr._i({}, "a") == 0


def test__s_str_truthy_and_default():
    assert wr._s({"a": "x"}, "a") == "x"
    assert wr._s({"a": ""}, "a", "d") == "d"
    assert wr._s({"a": 123}, "a", "d") == "d"
    assert wr._s({}, "a") == ""


def test__mtime_oserror_returns_zero():
    assert wr._mtime(os.path.join(WF_DIR, "no-such-file.json")) == 0.0


def test__session_of_without_workflows_segment():
    assert wr._session_of(os.path.join("a", "b", "c")) == ""


def test__text_of_all_shapes():
    assert wr._text_of({"content": "plain"}) == "plain"
    assert (
        wr._text_of(
            {"content": [{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]}
        )
        == "a\nb"
    )
    assert wr._text_of({"content": [{"type": "tool_use", "id": "x"}]}) == ""
    assert wr._text_of({"content": 123}) == ""
    assert wr._text_of({}) == ""


# ───────────────────────── parse_manifest defensive branches ─────────────────────────
def test_parse_manifest_oserror_returns_none():
    assert wr.parse_manifest(os.path.join(WF_DIR, "missing.json")) is None


def test_parse_manifest_bad_json_returns_none(tmp_path):
    p = tmp_path / "wf_bad.json"
    p.write_text("{not valid json", encoding="utf-8")
    assert wr.parse_manifest(str(p)) is None


def test_parse_manifest_non_dict_returns_none(tmp_path):
    p = tmp_path / "wf_list.json"
    p.write_text("[1, 2, 3]", encoding="utf-8")
    assert wr.parse_manifest(str(p)) is None


def test_parse_manifest_skips_phase_and_junk_entries():
    # the fixture manifest carries 2 workflow_phase entries + a bare-string junk entry that
    # must all be skipped, leaving exactly the 3 workflow_agent rows
    run = wr.parse_manifest(MANIFEST)
    assert run is not None
    assert [a.agent_id for a in run.agents] == [
        "agent-kitchensink",
        "agent-secretcheck",
        "agent-taskorder",
    ]
    assert run.phases == ["Investigate", "Synthesize"]


def test_parse_manifest_string_phases_and_no_wf_prefix(tmp_path):
    p = tmp_path / "custom-name.json"  # no wf_ prefix -> wf_id falls back to basename
    p.write_text(
        json.dumps(
            {"status": "completed", "phases": ["Alpha", "Beta"], "workflowProgress": []}
        ),
        encoding="utf-8",
    )
    run = wr.parse_manifest(str(p))
    assert run is not None
    assert run.phases == ["Alpha", "Beta"]  # non-dict phase elements pass through
    assert run.wf_id == "custom-name.json"
    assert run.agents == []


# ───────────────────────── WFAgent / WFRun derived branches ─────────────────────────
def _agents_by_label(run):
    return {a.label: a for a in run.agents}


def test_agent_state_property_branches():
    run = wr.parse_manifest(MANIFEST)
    by = _agents_by_label(run)
    assert by["taskorder"].running is True  # state 'progress'
    assert by["kitchensink"].running is False  # state 'done'
    assert by["secretcheck"].errored is True  # state 'error'
    assert by["secretcheck"].retrying is True  # attempt == 2
    assert by["kitchensink"].retrying is False  # attempt == 1


def test_run_active_true_and_counts_all_buckets():
    run = wr.parse_manifest(MANIFEST)
    assert run.active is True  # status 'running' is non-terminal
    # LIVE-run control: the fix must not zero the running counter everywhere.
    assert run.counts == {
        "running": 1,
        "done": 1,
        "error": 1,
        "orphaned": 0,
        "total": 3,
    }


def _run_with_states(tmp_path, status, states):
    path = tmp_path / f"wf_{status}.json"
    rows = [
        {"type": "workflow_agent", "agentId": f"a{i}", "label": f"a{i}", "state": state}
        for i, state in enumerate(states)
    ]
    path.write_text(
        json.dumps({"status": status, "phases": [], "workflowProgress": rows}),
        encoding="utf-8",
    )
    run = wr.parse_manifest(str(path))
    assert run is not None
    return run


def test_terminal_agents_orphaned_with_live_control(tmp_path):
    """Killed fails on buggy code; live is the control that passes on both versions."""
    states = ["done", "error", "start", "progress"]
    killed = _run_with_states(tmp_path, "killed", states)
    live = _run_with_states(tmp_path, "running", states)
    assert killed.counts == {
        "running": 0,
        "done": 1,
        "error": 1,
        "orphaned": 2,
        "total": 4,
    }
    assert live.counts == {
        "running": 2,
        "done": 1,
        "error": 1,
        "orphaned": 0,
        "total": 4,
    }


def test_every_terminal_status_orphans_unfinished_agent(tmp_path):
    for status in wr._TERMINAL_RUN:
        counts = _run_with_states(tmp_path, status, ["progress"]).counts
        assert counts["running"] == 0
        assert counts["orphaned"] == 1


def test_fleet_rollup_separates_live_and_orphaned(tmp_path):
    roll = wr.fleet_rollup(
        [
            _run_with_states(tmp_path, "failed", ["progress"]),
            _run_with_states(tmp_path, "running", ["progress"]),
        ]
    )
    assert roll["running"] == 1
    assert roll["orphaned"] == 1
    assert "orphaned" in roll


def test_counts_invariant_for_live_and_terminal_runs(tmp_path):
    for status in ["running", *wr._TERMINAL_RUN]:
        counts = _run_with_states(
            tmp_path, status, ["done", "error", "progress"]
        ).counts
        assert (
            sum(counts[key] for key in ("running", "done", "error", "orphaned"))
            == counts["total"]
        )


# ───────────────────────── FleetPoller defensive branches ─────────────────────────
def test_poller_active_filters_both_arcs():
    # export root -> one active run (True arc)
    active = wr.FleetPoller(EXPORT_PROJECTS).active()
    assert [r.wf_id for r in active] == [WF_ID]
    # schema-lock root -> one completed run -> filtered out (False arc)
    assert wr.FleetPoller(LOCK_ROOT).active() == []


def test_poller_skips_unparseable_manifest(tmp_path):
    root = tmp_path / "projects" / "proj" / "sess" / "workflows"
    root.mkdir(parents=True)
    (root / "wf_bad.json").write_text("{broken", encoding="utf-8")
    poller = wr.FleetPoller(str(tmp_path / "projects"))
    assert poller.poll() == []  # parse returned None -> not stored


def test_poller_removes_gone_manifest(tmp_path):
    wfdir = tmp_path / "projects" / "proj" / "sess" / "workflows"
    wfdir.mkdir(parents=True)
    man = wfdir / "wf_gone.json"
    man.write_text(
        json.dumps({"status": "running", "workflowProgress": []}), encoding="utf-8"
    )
    poller = wr.FleetPoller(str(tmp_path / "projects"))
    assert [r.wf_id for r in poller.poll()] == ["wf_gone"]
    man.unlink()
    assert poller.poll() == []  # gone-manifest removal loop


# ───────────────────────── journal_states defensive branches ─────────────────────────
def test_journal_states_precedence_and_skips(tmp_path):
    j = tmp_path / "journal.jsonl"
    j.write_text(
        '{"type":"result","agentId":"a","result":"done"}\n'
        '{"type":"started","agentId":"a"}\n'  # 'a' already result -> stays result
        '{"type":"noise-without-agentid"}\n'  # no agentId -> skipped
        "not-json-line\n"  # JSONDecodeError -> skipped
        '{"type":"started","agentId":"b"}\n',
        encoding="utf-8",
    )
    assert wr.journal_states(str(tmp_path)) == {"a": "result", "b": "started"}


def test_journal_states_oserror_returns_empty(tmp_path):
    # a dir with no journal.jsonl -> open raises OSError -> {}
    assert wr.journal_states(str(tmp_path)) == {}


# ───────────────────────── journal_result defensive branches ─────────────────────────
def test_journal_result_str_from_fixture():
    r = wr.journal_result(WF_DIR, "agent-kitchensink")
    assert r.startswith("# Kitchensink Report")


def test_journal_result_dict_and_null_and_malformed(tmp_path):
    j = tmp_path / "journal.jsonl"
    j.write_text(
        "not-json\n"  # JSONDecodeError -> skipped
        '{"type":"result","agentId":"a","result":null}\n'  # result None -> skipped, continue
        '{"type":"result","agentId":"a","result":{"k":"v","n":1}}\n',  # dict -> json.dumps
        encoding="utf-8",
    )
    out = wr.journal_result(str(tmp_path), "a")
    assert json.loads(out) == {"k": "v", "n": 1}


def test_journal_result_missing_agent_returns_empty():
    assert wr.journal_result(WF_DIR, "agent-nonexistent") == ""


def test_journal_result_oserror_returns_empty(tmp_path):
    assert wr.journal_result(str(tmp_path), "a") == ""  # no journal.jsonl


# ───────────────────────── agent_output branches ─────────────────────────
def test_agent_output_journal_result_wins():
    out = wr.agent_output(
        os.path.join(WF_DIR, "agent-kitchensink.jsonl"), WF_DIR, "agent-kitchensink"
    )
    assert out.startswith("# Kitchensink Report")


def test_agent_output_transcript_fallback_when_no_journal_result():
    # taskorder has a 'started' journal row but no 'result' -> fall back to last assistant text
    out = wr.agent_output(
        os.path.join(WF_DIR, "agent-taskorder.jsonl"), WF_DIR, "agent-taskorder"
    )
    assert out == "working on the ordered task"


def test_agent_output_empty_without_assistants(tmp_path):
    p = tmp_path / "agent-user.jsonl"
    p.write_text(
        '{"type":"user","message":{"content":"just a user"}}\n', encoding="utf-8"
    )
    assert wr.agent_output(str(p)) == ""


# ───────────────────────── agent_transcript branches ─────────────────────────
def test_agent_transcript_mixed_and_skips(tmp_path):
    p = tmp_path / "agent-t.jsonl"
    p.write_text(
        '{"type":"user","message":{"content":"hello user"}}\n'
        "\n"  # blank line -> skipped
        "not json\n"  # JSONDecodeError -> skipped
        '{"type":"assistant","message":{"content":"hello assistant"}}\n'
        '{"type":"system","message":{"content":"system text, non-empty, neither user nor assistant"}}\n'  # text but type is neither -> falls through both branches
        '{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"x","content":"r"}]}}\n',  # empty text -> skipped
        encoding="utf-8",
    )
    users, assistants = wr.agent_transcript(str(p))
    assert users == ["hello user"]
    assert assistants == ["hello assistant"]


def test_agent_transcript_oserror_returns_empty_lists():
    users, assistants = wr.agent_transcript(os.path.join(WF_DIR, "missing.jsonl"))
    assert users == [] and assistants == []


# ───────────────────────── agent_prompt branches ─────────────────────────
def test_agent_prompt_empty_when_no_users():
    assert wr.agent_prompt(os.path.join(WF_DIR, "missing.jsonl")) == ""


def test_agent_prompt_returns_largest_user_message():
    prompt = wr.agent_prompt(os.path.join(WF_DIR, "agent-taskorder.jsonl"))
    assert prompt.startswith("This is a much larger later user message")
