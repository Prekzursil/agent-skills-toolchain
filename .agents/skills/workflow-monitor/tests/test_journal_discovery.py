import json
import os

import pytest

import workflow_run as wr


def make_journal(tmp_path, wf_id="wf_test", records=None, age=1, transcript_age=None):
    wf_dir = tmp_path / "project" / "session" / "subagents" / "workflows" / wf_id
    wf_dir.mkdir(parents=True)
    journal = wf_dir / "journal.jsonl"
    records = records or [{"type": "started", "agentId": "abcdef123456"}]
    journal.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    now = 1_000_000.0
    os.utime(journal, (now - age, now - age))
    if transcript_age is not None:
        transcript = wf_dir / "agent-abcdef123456.jsonl"
        transcript.write_text("{}\n", encoding="utf-8")
        os.utime(transcript, (now - transcript_age, now - transcript_age))
    return wf_dir, now


def make_manifest(tmp_path, wf_id="wf_test", status="killed", mtime=None, **fields):
    """A manifest for the same tree ``make_journal`` builds (kill-stamp shape by default)."""
    manifest_dir = tmp_path / "project" / "session" / "workflows"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest = manifest_dir / f"{wf_id}.json"
    body = {
        "workflowName": "authoritative",
        "status": status,
        "agentCount": 0,
        "totalTokens": 77,
        **fields,
    }
    manifest.write_text(json.dumps(body), encoding="utf-8")
    if mtime is not None:
        os.utime(manifest, (mtime, mtime))
    return manifest


def test_fresh_journal_only_run_is_active_and_rolled_up(tmp_path, monkeypatch):
    wf_dir, now = make_journal(tmp_path)
    monkeypatch.setattr(
        wr.time if hasattr(wr, "time") else __import__("time"), "time", lambda: now
    )
    runs = wr.FleetPoller(str(tmp_path)).poll()
    assert [r.wf_id for r in runs] == [wf_dir.name]
    assert runs[0].status == "running" and runs[0].active
    assert wr.fleet_rollup(runs)["active_runs"] == 1


def test_idle_journal_is_retained_but_not_active(tmp_path):
    wf_dir, now = make_journal(tmp_path, age=600)
    run = wr.parse_journal_run(str(wf_dir), now=now)
    assert run.status == "idle" and not run.active


def test_journal_older_than_retention_is_not_surfaced(tmp_path, monkeypatch):
    _, now = make_journal(tmp_path, age=wr.JOURNAL_RETENTION_S + 1)
    monkeypatch.setattr(__import__("time"), "time", lambda: now)
    assert wr.FleetPoller(str(tmp_path)).poll() == []


def test_fresh_transcript_keeps_run_active_when_journal_is_stale(tmp_path):
    # Measured live journal ages were 1367/2127/992 s while transcript ages were 1/1/4 s.
    wf_dir, now = make_journal(tmp_path, age=2127, transcript_age=4)
    run = wr.parse_journal_run(str(wf_dir), now=now)
    assert run.active and run.mtime == pytest.approx(now - 4)


def test_manifest_wins_over_same_id_journal(tmp_path, monkeypatch):
    """Manifest authority, correctly scoped after the WF-1 refutation.

    REFUTED 2026-08-18: this test's earlier precedence wording — "the manifest WINS
    over a same-id journal", unconditionally — was disproven by re-executing the live
    repro: the estate's runtime kill-stamps manifests MID-RUN, so one stale terminal
    manifest permanently blinded the board to 2 live runs / 56 executing agents. What
    SURVIVES, pinned here: the manifest wins METADATA always (name/tokens, one run, no
    second journal-derived run), and wins STATUS exactly when its own mtime is >= the
    journal dir's newest write (final-flush ordering) or the journal is stale. The
    journal leads liveness only when it outwrote the manifest within
    JOURNAL_ACTIVE_WINDOW_S — see
    test_kill_stamped_manifest_with_live_journal_renders_active.
    """
    wf_dir, now = make_journal(tmp_path, wf_id="wf_same")
    make_manifest(tmp_path, wf_id="wf_same", status="completed", mtime=now)
    monkeypatch.setattr(__import__("time"), "time", lambda: now)
    # Journal-folding poller: the journal (now-1) PREDATES the manifest stamp (now),
    # so the terminal status stands even though the journal is within the window.
    runs = wr.FleetPoller(str(tmp_path)).poll()
    assert (
        len(runs) == 1
        and runs[0].name == "authoritative"
        and runs[0].total_tokens == 77
    )
    assert runs[0].status == "completed" and runs[0].manifest_status == ""
    assert runs[0].active is False
    assert runs[0].wf_dir == "" and wf_dir.name == runs[0].wf_id
    # The legacy manifest-only mode never consults the journal at all.
    runs_nf = wr.FleetPoller(str(tmp_path), journal=False).poll()
    assert len(runs_nf) == 1 and runs_nf[0].status == "completed"
    assert runs_nf[0].manifest_status == "" and runs_nf[0].agents == []


def test_agent_states_and_anti_stall_guarantee(tmp_path):
    records = [
        {"type": "started", "agentId": "doneagent"},
        {"type": "result", "agentId": "doneagent", "result": "ok"},
        {"type": "started", "agentId": "liveagent"},
    ]
    wf_dir, now = make_journal(tmp_path, records=records)
    active = wr.parse_journal_run(str(wf_dir), now=now)
    assert [a.state for a in active.agents] == ["done", "running"]
    assert all(a.started_at == a.last_progress_at == 0 for a in active.agents)
    assert all(a.idle_ms(now * 1000) == 0.0 for a in active.agents)
    idle = wr.parse_journal_run(str(wf_dir), now=now + 600)
    assert [a.state for a in idle.agents] == ["done", "unknown"]


def test_subagents_dir_for_both_sources(tmp_path):
    wf_dir, now = make_journal(tmp_path)
    journal_run = wr.parse_journal_run(str(wf_dir), now=now)
    assert journal_run.subagents_dir() == str(wf_dir)
    manifest = tmp_path / "project" / "session" / "workflows" / "wf_m.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text("{}", encoding="utf-8")
    assert wr.parse_manifest(str(manifest)).subagents_dir() == str(
        tmp_path / "project" / "session" / "subagents" / "workflows" / "wf_m"
    )


def test_model_is_loaded_and_missing_or_malformed_is_empty(tmp_path):
    records = [{"type": "started", "agentId": x} for x in ("good", "missing", "bad")]
    wf_dir, now = make_journal(tmp_path, records=records)
    (wf_dir / "agent-good.meta.json").write_text('{"model":"opus"}', encoding="utf-8")
    (wf_dir / "agent-bad.meta.json").write_text("{", encoding="utf-8")
    assert [a.model for a in wr.parse_journal_run(str(wf_dir), now=now).agents] == [
        "opus",
        "",
        "",
    ]


def test_defensive_journal_paths(tmp_path, monkeypatch):
    missing = tmp_path / "missing"
    assert wr.parse_journal_run(str(missing)) is None
    assert wr._dir_last_write(str(missing)) == 0.0
    wf_dir = tmp_path / "p" / "s" / "subagents" / "workflows" / "wf_bad"
    wf_dir.mkdir(parents=True)
    (wf_dir / "journal.jsonl").write_text("{\n[]\n{}\n", encoding="utf-8")
    assert wr.parse_journal_run(str(wf_dir)) is None
    monkeypatch.setattr(wr.glob, "glob", lambda *_: (_ for _ in ()).throw(OSError()))
    assert wr.iter_journal_dirs(str(tmp_path)) == []
    assert wr._dir_last_write(str(wf_dir)) == 0.0


def test_iter_journal_dirs_ignores_non_dirs_and_missing_journal(tmp_path, monkeypatch):
    wf_dir, _ = make_journal(tmp_path)
    no_journal = wf_dir.parent / "wf_empty"
    no_journal.mkdir()
    fake = wf_dir.parent / "wf_file"
    fake.write_text("x", encoding="utf-8")
    assert wr.iter_journal_dirs(str(tmp_path)) == [str(wf_dir)]
    monkeypatch.setattr(
        wr.os.path, "isdir", lambda *_: (_ for _ in ()).throw(OSError())
    )
    assert wr.iter_journal_dirs(str(tmp_path)) == []


def test_journal_poller_is_o_changed(tmp_path, monkeypatch):
    records = [
        {"type": "started", "agentId": "done"},
        {"type": "result", "agentId": "done"},
        {"type": "started", "agentId": "live"},
    ]
    _, now = make_journal(tmp_path, records=records)
    monkeypatch.setattr(__import__("time"), "time", lambda: now)
    original = wr.parse_journal_run
    calls = []
    monkeypatch.setattr(
        wr, "parse_journal_run", lambda *a, **k: (calls.append(1), original(*a, **k))[1]
    )
    poller = wr.FleetPoller(str(tmp_path))
    poller.poll()
    poller.poll()
    assert len(calls) == 1
    monkeypatch.setattr(__import__("time"), "time", lambda: now + 600)
    aged = poller.poll()[0]
    assert aged.status == "idle"
    assert [a.state for a in aged.agents] == ["done", "unknown"]
    assert len(calls) == 1


def test_journal_run_is_evicted_when_directory_disappears(tmp_path, monkeypatch):
    wf_dir, now = make_journal(tmp_path)
    monkeypatch.setattr(__import__("time"), "time", lambda: now)
    poller = wr.FleetPoller(str(tmp_path))
    assert poller.poll()
    monkeypatch.setattr(wr, "iter_journal_dirs", lambda *_: [])
    assert poller.poll() == []


def test_defensive_metadata_and_failed_parse_are_ignored(tmp_path, monkeypatch):
    wf_dir, now = make_journal(tmp_path)
    (wf_dir / "agent-abcdef123456.meta.json").write_text("[]", encoding="utf-8")
    assert wr.parse_journal_run(str(wf_dir), now=now).agents[0].model == ""
    monkeypatch.setattr(__import__("time"), "time", lambda: now)
    monkeypatch.setattr(wr, "parse_journal_run", lambda *a, **k: None)
    assert wr.FleetPoller(str(tmp_path)).poll() == []


def test_existing_journal_delta_defensive_branches(tmp_path, monkeypatch):
    states = {}
    wr._fold_journal_record(states, [])
    assert states == {}
    path = tmp_path / "delta.jsonl"
    path.write_bytes(b'{"agentId":"a"}')
    assert wr.read_journal_delta(str(path), 0) == (0, [])
    path.write_bytes(b'\n{bad}\n{"agentId":"a"}\n')
    offset, records = wr.read_journal_delta(str(path), 999)
    assert offset == path.stat().st_size and records == [{"agentId": "a"}]
    real_open = open
    monkeypatch.setattr(
        "builtins.open",
        lambda *a, **k: (
            (_ for _ in ()).throw(OSError())
            if a and os.fspath(a[0]) == str(path)
            else real_open(*a, **k)
        ),
    )
    assert wr.read_journal_delta(str(path), 0) == (0, [])


# ───────── journal-led liveness for manifest-backed runs (WF-1 refutation fix) ─────────
_KILL_RECORDS = [
    {"type": "started", "agentId": "doneagent"},
    {"type": "result", "agentId": "doneagent", "result": "ok"},
    {"type": "started", "agentId": "liveagent"},
]


def test_kill_stamped_manifest_with_live_journal_renders_active(tmp_path, monkeypatch):
    """REQUIRED both-states test 1 — the WF-1 refutation's live fixture, reduced.

    A terminal manifest (status=killed, agents=0) stamped at T while the journal dir
    keeps writing at T+delta within JOURNAL_ACTIVE_WINDOW_S: LIVENESS is journal-led
    (run active, started-with-no-result agents running, fleet rollup counts it), while
    METADATA stays manifest-led (name/tokens) and no second run is synthesized.
    """
    wf_dir, now = make_journal(
        tmp_path, wf_id="wf_kill", records=_KILL_RECORDS, age=2, transcript_age=1
    )
    make_manifest(tmp_path, wf_id="wf_kill", status="killed", mtime=now - 30)
    monkeypatch.setattr(__import__("time"), "time", lambda: now)
    runs = wr.FleetPoller(str(tmp_path)).poll()
    assert len(runs) == 1  # the same-id journal dir never becomes a second run
    run = runs[0]
    assert run.active is True and run.status == "running"
    assert run.manifest_status == "killed"  # the manifest's own word, preserved
    assert (
        run.name == "authoritative" and run.total_tokens == 77
    )  # metadata manifest-led
    assert wr.fleet_rollup(runs)["active_runs"] == 1
    by = {a.agent_id: a for a in run.agents}
    assert by["liveagent"].running is True and by["liveagent"].lost is False
    assert by["liveagent"].state == "started"
    assert by["doneagent"].state == "done"
    c = run.counts
    assert c["running"] == 1 and c["orphaned"] == 0 and c["done"] == 1


def test_kill_stamped_manifest_with_stale_journal_stays_killed(tmp_path, monkeypatch):
    """REQUIRED both-states test 2 — same manifest, journal writes OUTSIDE the window.

    The journal outwrote the manifest stamp (now-400 > now-500) but the newest write is
    older than JOURNAL_ACTIVE_WINDOW_S, so the manifest's death verdict stands and the
    started-with-no-result journal agent is lost/orphaned. Pins that the fix cannot
    resurrect the ancient orphans: recency is the ONLY promoter, exactly like
    parse_journal_run — staleness never invents anything, it just leaves the manifest's
    own word in place.
    """
    make_journal(
        tmp_path,
        wf_id="wf_kill",
        records=[{"type": "started", "agentId": "liveagent"}],
        age=400,
    )
    now = 1_000_000.0
    make_manifest(tmp_path, wf_id="wf_kill", status="killed", mtime=now - 500)
    monkeypatch.setattr(__import__("time"), "time", lambda: now)
    runs = wr.FleetPoller(str(tmp_path)).poll()
    (run,) = runs
    assert run.active is False and run.status == "killed"
    assert run.manifest_status == ""  # no override was ever in effect
    assert wr.fleet_rollup(runs)["active_runs"] == 0
    by = {a.agent_id: a for a in run.agents}
    assert by["liveagent"].state == "lost" and by["liveagent"].lost is True
    assert run.counts["orphaned"] == 1 and run.counts["running"] == 0


def test_liveness_override_lapses_back_to_the_manifest_verdict(tmp_path, monkeypatch):
    """Both directions of the flip on ONE long-lived poller.

    While the journal outwrites the kill-stamp the run renders running; once the
    recency lapses the status RESTORES to the manifest's own word — death is the
    manifest's verdict, never an mtime inference — and unfinished journal-only rows
    restamp lost. A second poll while live holds the override without duplicating
    rows, and neither manifest rows nor journal rows with a result are ever restamped.
    """
    wf_dir, now = make_journal(tmp_path, wf_id="wf_flip", records=_KILL_RECORDS, age=2)
    make_manifest(
        tmp_path,
        wf_id="wf_flip",
        status="killed",
        mtime=now - 30,
        workflowProgress=[
            {"type": "workflow_agent", "agentId": "m1", "label": "m1", "state": "done"}
        ],
    )
    fake = {"now": now}
    monkeypatch.setattr(__import__("time"), "time", lambda: fake["now"])
    poller = wr.FleetPoller(str(tmp_path))
    (run,) = poller.poll()
    assert run.status == "running" and run.manifest_status == "killed"
    (run,) = poller.poll()  # steady state while live: override held, no duplicates
    assert run.status == "running" and run.manifest_status == "killed"
    assert [a.agent_id for a in run.agents] == ["m1", "doneagent", "liveagent"]
    by = {a.agent_id: a for a in run.agents}
    assert by["liveagent"].state == "started" and by["liveagent"].lost is False
    fake["now"] = now + wr.JOURNAL_ACTIVE_WINDOW_S + 60
    (run,) = poller.poll()
    assert run.status == "killed" and run.active is False
    assert run.manifest_status == ""
    by = {a.agent_id: a for a in run.agents}
    assert by["liveagent"].state == "lost" and by["liveagent"].lost is True
    assert (
        by["doneagent"].state == "done"
    )  # journal rows with a result: never restamped
    assert by["m1"].state == "done"  # manifest rows: never restamped
    assert run.counts["orphaned"] == 1 and run.counts["done"] == 2


def test_liveness_probe_cadence_for_long_dead_dirs(tmp_path, monkeypatch):
    """Once a journal dir is long-dead (>2x the window), the full probe relaxes to one
    per _LIVENESS_REPROBE_S — the cache can only DELAY a promotion, never invent a
    death verdict — and a long-dead run that RESUMES is promoted within one cadence.
    """
    wf_dir, now = make_journal(
        tmp_path,
        wf_id="wf_dead",
        records=[{"type": "started", "agentId": "liveagent"}],
        age=5000,
    )
    make_manifest(tmp_path, wf_id="wf_dead", status="killed", mtime=now - 6000)
    fake = {"now": now}
    monkeypatch.setattr(__import__("time"), "time", lambda: fake["now"])
    poller = wr.FleetPoller(str(tmp_path))
    calls = []
    original = wr._dir_last_write
    monkeypatch.setattr(
        wr, "_dir_last_write", lambda p: (calls.append(p), original(p))[1]
    )
    (run,) = poller.poll()
    assert run.status == "killed"
    first = len(calls)  # first sight always probes (no cached verdict yet)
    (run,) = poller.poll()  # long-dead + cadence not due -> NO new probe
    assert len(calls) == first
    assert run.status == "killed"
    fake["now"] = now + wr._LIVENESS_REPROBE_S + 1
    journal = wf_dir / "journal.jsonl"  # the run RESUMES: journal outwrites the stamp
    os.utime(journal, (fake["now"] - 1, fake["now"] - 1))
    (run,) = poller.poll()  # cadence due -> re-probe -> promoted
    assert len(calls) > first
    assert run.status == "running" and run.active is True
    by = {a.agent_id: a for a in run.agents}
    assert by["liveagent"].state == "started" and by["liveagent"].lost is False
