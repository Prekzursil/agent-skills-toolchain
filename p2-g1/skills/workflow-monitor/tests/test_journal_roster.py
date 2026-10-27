#!/usr/bin/env python3
"""WF-4: the journal is the ROSTER, not just a status side-channel.

MEASURED DEFECT (wf_e58dfd3f-7b1, completed, manifest era): the manifest carried 50
``workflow_agent`` rows — all ``attempt=1``, so not retries — while ``journal.jsonl``
recorded **80** distinct started agentIds and **80** ``agent-*.jsonl`` transcripts sat on
disk. Two mechanically independent signals agreed that 30 real agents (245-483 KB of
transcript each, every one ``started`` with no ``result``) were invisible to the board.
Fleet-wide the same probe found **2,242** invisible agents across **107 of 865** runs.

These tests pin the three pieces that close it — the incremental reader, the roster
reconciler, and the poller wiring — including every defensive branch, since
``workflow_run`` is gated at 100% branch coverage.
"""

from __future__ import annotations

import builtins
import json
import os

import workflow_run as wr


def _write(path, *records):
    """Write journal records as raw text (str passed through verbatim)."""
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        for r in records:
            fh.write(r if isinstance(r, str) else json.dumps(r) + "\n")


def _manifest(path, status, agents):
    path.write_text(
        json.dumps(
            {
                "status": status,
                "workflowProgress": [dict(type="workflow_agent", **a) for a in agents],
            }
        ),
        encoding="utf-8",
    )


# ───────────────────────── _fold_journal_record ─────────────────────────
def test_fold_journal_record_ignores_non_dict():
    out: dict = {}
    wr._fold_journal_record(out, [1, 2, 3])  # a bare JSON array is not a record
    wr._fold_journal_record(out, 7)
    assert out == {}


def test_fold_journal_record_result_wins_and_never_regresses():
    out: dict = {}
    wr._fold_journal_record(out, {"type": "started", "agentId": "a"})
    assert out == {"a": "started"}
    wr._fold_journal_record(out, {"type": "result", "agentId": "a"})
    wr._fold_journal_record(out, {"type": "started", "agentId": "a"})  # cannot regress
    assert out == {"a": "result"}
    wr._fold_journal_record(out, {"type": "started"})  # no agentId -> skipped
    assert out == {"a": "result"}


def test_journal_states_survives_a_bare_scalar_line(tmp_path):
    """A valid-JSON, non-dict line used to reach ``.get`` and raise AttributeError."""
    _write(
        str(tmp_path / "journal.jsonl"),
        "5\n",
        {"type": "started", "agentId": "a"},
    )
    assert wr.journal_states(str(tmp_path)) == {"a": "started"}


# ───────────────────────── read_journal_delta ─────────────────────────
def test_delta_missing_file_returns_cursor_unmoved(tmp_path):
    assert wr.read_journal_delta(str(tmp_path / "nope.jsonl"), 11) == (11, [])


def test_delta_nothing_appended(tmp_path):
    j = tmp_path / "journal.jsonl"
    _write(str(j), {"type": "started", "agentId": "a"})
    size = j.stat().st_size
    assert wr.read_journal_delta(str(j), size) == (size, [])


def test_delta_reads_only_the_appended_tail(tmp_path):
    j = tmp_path / "journal.jsonl"
    _write(str(j), {"type": "started", "agentId": "a"})
    off, recs = wr.read_journal_delta(str(j), 0)
    assert [r["agentId"] for r in recs] == ["a"]
    with open(j, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({"type": "result", "agentId": "a"}) + "\n")
        fh.write(json.dumps({"type": "started", "agentId": "b"}) + "\n")
    off2, recs2 = wr.read_journal_delta(str(j), off)
    assert [r["agentId"] for r in recs2] == ["a", "b"]  # ONLY the new bytes
    assert off2 == j.stat().st_size


def test_delta_truncated_file_rewinds_and_rereads(tmp_path):
    j = tmp_path / "journal.jsonl"
    _write(str(j), {"type": "started", "agentId": "a"})
    big = j.stat().st_size + 5_000  # a cursor past EOF => rotated/truncated
    off, recs = wr.read_journal_delta(str(j), big)
    assert [r["agentId"] for r in recs] == ["a"]
    assert off == j.stat().st_size


def test_delta_leaves_a_partial_line_for_the_next_poll(tmp_path):
    j = tmp_path / "journal.jsonl"
    with open(j, "w", encoding="utf-8", newline="\n") as fh:
        fh.write('{"type":"started","agentId":"a"}')  # no trailing newline yet
    assert wr.read_journal_delta(str(j), 0) == (0, [])  # cursor unmoved
    with open(j, "a", encoding="utf-8", newline="\n") as fh:
        fh.write("\n")
    off, recs = wr.read_journal_delta(str(j), 0)
    assert [r["agentId"] for r in recs] == ["a"]  # re-read once complete
    assert off == j.stat().st_size


def test_delta_skips_blank_and_malformed_lines(tmp_path):
    j = tmp_path / "journal.jsonl"
    _write(
        str(j),
        {"type": "started", "agentId": "a"},
        "\n",
        "   \n",
        "not-json\n",
        {"type": "result", "agentId": "a"},
    )
    _, recs = wr.read_journal_delta(str(j), 0)
    assert [r["type"] for r in recs] == ["started", "result"]


def test_delta_unreadable_file_returns_cursor_unmoved(tmp_path, monkeypatch):
    """getsize succeeds but the open fails (locked/racing writer) -> no new info."""
    j = tmp_path / "journal.jsonl"
    _write(str(j), {"type": "started", "agentId": "a"})
    real_open = builtins.open

    def boom(path, *a, **kw):
        if str(path) == str(j):
            raise OSError("locked")
        return real_open(path, *a, **kw)

    monkeypatch.setattr(builtins, "open", boom)
    assert wr.read_journal_delta(str(j), 0) == (0, [])


# ───────────────────────── reconcile_roster ─────────────────────────
def _run(status="completed", agents=()):
    return wr.WFRun(
        wf_id="wf_x",
        name="n",
        status=status,
        phases=[],
        agent_count=len(agents),
        total_tokens=0,
        total_tool_calls=0,
        duration_ms=0,
        started_at=0,
        manifest_path="",
        session="",
        mtime=0.0,
        agents=list(agents),
    )


def _agent(agent_id="m1", state="done"):
    return wr.WFAgent(
        agent_id=agent_id,
        index=0,
        label=agent_id,
        phase_index=0,
        phase_title="P",
        model="",
        state=state,
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


def test_reconcile_adds_the_agents_the_manifest_never_recorded():
    run = _run(agents=[_agent("m1")])
    added = wr.reconcile_roster(run, {"m1": "result", "j1": "started", "j2": "result"})
    assert added == 2
    assert len(run.agents) == 3
    by = {a.agent_id: a for a in run.agents}
    assert by["j1"].journal_only is True
    assert by["m1"].journal_only is False


def test_reconcile_stamps_journal_state_onto_manifest_rows():
    """The half the cockpit used to discard: the manifest row learns the journal's word."""
    run = _run(agents=[_agent("m1", state="progress")])
    wr.reconcile_roster(run, {"m1": "result"})
    assert run.agents[0].journal_state == "result"
    # an agent the journal is silent about is stamped empty, not left stale
    run2 = _run(agents=[_agent("m2", state="progress")])
    wr.reconcile_roster(run2, {})
    assert run2.agents[0].journal_state == ""


def test_reconcile_terminal_run_marks_started_agents_lost_not_running():
    """A finished run must never report phantom RUNNING agents (rule: no fake liveness)."""
    run = _run(status="completed")
    wr.reconcile_roster(run, {"j1": "started", "j2": "result"})
    by = {a.agent_id: a for a in run.agents}
    assert (by["j1"].state, by["j1"].lost) == ("lost", True)
    assert by["j1"].running is False
    assert (by["j2"].state, by["j2"].lost) == ("done", False)
    c = run.counts
    assert c["running"] == 0 and c["done"] == 1 and c["orphaned"] == 1
    assert c["running"] + c["done"] + c["error"] + c["orphaned"] == c["total"]


def test_reconcile_active_run_keeps_started_agents_running():
    run = _run(status="running")
    wr.reconcile_roster(run, {"j1": "started"})
    a = run.agents[0]
    assert (a.state, a.lost, a.running) == ("started", False, True)
    assert run.counts["running"] == 1


def test_reconcile_is_idempotent():
    run = _run(status="completed", agents=[_agent("m1")])
    states = {"m1": "result", "j1": "started"}
    assert wr.reconcile_roster(run, states) == 1
    assert wr.reconcile_roster(run, states) == 0  # no duplicate rows
    assert wr.reconcile_roster(run, states) == 0
    assert len(run.agents) == 2


def test_reconcile_labels_journal_only_rows_and_buckets_their_phase():
    run = _run(status="completed")
    wr.reconcile_roster(run, {"abcdef0123456": "started"})
    a = run.agents[0]
    assert a.label == "abcdef01"  # id-derived label, same fallback the parser uses
    assert a.phase_title == wr.JOURNAL_ONLY_PHASE
    assert a.phase_index == -1
    assert a.tokens == 0 and a.tool_calls == 0  # journal knows no metadata; claim none
    assert a.started_at == 0 and a.last_progress_at == 0  # never mtime-derived


# ───────────────────────── FleetPoller wiring ─────────────────────────
def _fleet(tmp_path, status="completed"):
    wfdir = tmp_path / "projects" / "proj" / "sess" / "workflows"
    wfdir.mkdir(parents=True)
    _manifest(
        wfdir / "wf_t.json",
        status,
        [{"agentId": "m1", "state": "done", "label": "m1"}],
    )
    jdir = tmp_path / "projects" / "proj" / "sess" / "subagents" / "workflows" / "wf_t"
    jdir.mkdir(parents=True)
    _write(
        str(jdir / "journal.jsonl"),
        {"type": "started", "agentId": "m1"},
        {"type": "result", "agentId": "m1"},
        {"type": "started", "agentId": "ghost"},
    )
    # Deterministic TERMINAL fixture: stamp the journal OLDER than the manifest so the
    # journal-led liveness override (WF-1 refutation fix) cannot promote this run —
    # these tests pin the ROSTER semantics of a genuinely finished run. (A test that
    # wants the override exercises it explicitly in test_journal_discovery.py.)
    man_mtime = os.path.getmtime(
        tmp_path / "projects" / "proj" / "sess" / "workflows" / "wf_t.json"
    )
    os.utime(jdir / "journal.jsonl", (man_mtime - 120, man_mtime - 120))
    return str(tmp_path / "projects"), jdir


def test_poller_folds_the_journal_roster_in_by_default(tmp_path):
    root, _ = _fleet(tmp_path)
    (run,) = wr.FleetPoller(root).poll()
    assert {a.agent_id for a in run.agents} == {"m1", "ghost"}
    assert run.counts["total"] == 2
    assert run.counts["orphaned"] == 1  # terminal run, started with no result


def test_poller_journal_false_keeps_the_manifest_only_roster(tmp_path):
    root, _ = _fleet(tmp_path)
    (run,) = wr.FleetPoller(root, journal=False).poll()
    assert {a.agent_id for a in run.agents} == {"m1"}  # the defect, preserved on demand


def test_poller_repolls_without_duplicating_then_sees_new_records(tmp_path):
    """Second poll: no new bytes, nothing re-parsed -> roster stable (the skip arc)."""
    root, jdir = _fleet(tmp_path)
    poller = wr.FleetPoller(root)
    (run,) = poller.poll()
    assert len(run.agents) == 2
    (run,) = poller.poll()
    assert len(run.agents) == 2  # not re-added
    with open(jdir / "journal.jsonl", "a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({"type": "started", "agentId": "late"}) + "\n")
    (run,) = poller.poll()
    assert {a.agent_id for a in run.agents} == {"m1", "ghost", "late"}


def test_poller_reparsed_manifest_rebuilds_the_journal_rows(tmp_path):
    """A re-parsed manifest yields a fresh WFRun with no stamps; it must be re-reconciled."""
    root, _ = _fleet(tmp_path)
    poller = wr.FleetPoller(root)
    (run,) = poller.poll()
    assert len(run.agents) == 2
    man = os.path.join(root, "proj", "sess", "workflows", "wf_t.json")
    st = os.stat(man)
    os.utime(man, (st.st_atime, st.st_mtime + 10))  # bump mtime -> re-parse
    (run2,) = poller.poll()
    assert {a.agent_id for a in run2.agents} == {"m1", "ghost"}
    assert run2.agents[0].journal_state == "result"  # stamps restored on the fresh row
