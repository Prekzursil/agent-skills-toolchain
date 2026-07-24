"""Tests for ``monitorcore.databricks_source`` — the DatabricksSource adapter.

COVERAGE: COMPLETE — 42 tests, measured GREEN against
``monitorcore/databricks_source.py`` at 100% line + 100% branch
(``pytest --cov=monitorcore.databricks_source --cov-branch``), ruff 0.15.17
check + format clean, basedpyright 1.39.8 standard mode 0 errors.

Red-then-green provenance: a 36-name skeleton failed 36/36 by construction; these
bodies then failed at collection (``ModuleNotFoundError``) before the module existed.
Three mutations were re-applied against the finished code to prove the tests bite —
(a) collapsing the discriminator to silence alone → 7 RED, led by
``test_thinking_while_transcript_silent_but_tool_active_is_not_stalled``;
(b) letting ``poll`` raise → 3 RED, all the never-raise tests;
(c) freezing the busy glyph to a constant → 1 RED, exactly
``test_busy_glyph_is_not_decorative_dead_agent_is_not_busy``. Each was reverted
immediately and the suite re-verified green.

These tests are HERMETIC with respect to the parallel-agent siblings: ``_source``
passes ``events_mod=None`` / ``completion_mod=None``, so no assertion here depends on
whether ``dbx_events`` / ``dbx_completion`` exist or what they currently do.

Proves the two cardinal invariants and the eight-state unit liveness machine:

* **poll never raises** — missing file, unreadable path (a REAL ``OSError`` from
  ``open()`` on a directory), an injected locked-file reader, and a simulated API
  failure each yield a stale / unreachable :class:`Snapshot` with the last-good payload
  retained. ``BaseException`` (Ctrl-C) is deliberately NOT swallowed.
* **payload is never flattened** — :class:`DbxPayload` carries native
  :class:`DbxUnit` dataclasses, and the eight-state liveness vocabulary lives INSIDE
  the payload; ``SourceState`` gains no new constant.
* the THINKING-vs-STALLED discriminator combines seven signals (last event, heartbeat,
  lifecycle status, artifact growth, tool-call state, lease renewal, retry state) and
  NEVER calls silence STALLED while a tool call or a remote task is active.
* the busy indicator is a pure function of real arrival — a dead agent is never busy.
"""

from __future__ import annotations

import ast
import dataclasses
import json
from pathlib import Path

import pytest

from monitorcore.contract import MonitorSource, Snapshot, SourceState
from monitorcore.databricks_source import (
    DatabricksSource,
    DbxPayload,
    DbxUnit,
    Liveness,
    LivenessThresholds,
    busy_glyph,
    default_events_path,
    derive_liveness,
    is_busy,
)
from monitorcore.render_md import render_md

NOW = 1_784_283_000.0
SK_TOKEN = "sk-" + "c" * 20  # programmatic, never a literal secret shape

# Tight, explicit thresholds so every assertion below is arithmetic, not a guess.
TH = LivenessThresholds(
    heartbeat_late_s=90.0,
    stalled_s=300.0,
    busy_window_s=30.0,
    starting_grace_s=20.0,
)


# ───────────────────────── builders ─────────────────────────
def _unit(**kw) -> DbxUnit:
    """A RUNNING unit whose every arrival channel is quiet unless overridden."""
    base = dict(
        unit_id="u1",
        run_id="r1",
        task_status="RUNNING",
        started_ts=NOW - 10_000,
        last_event_ts=NOW - 10_000,
        heartbeat_ts=NOW - 10_000,
    )
    base.update(kw)
    return DbxUnit(**base)  # type: ignore[arg-type]


def _rec(kind: str, ts: float, unit: str = "u1", run: str = "r1", **kw) -> dict:
    rec = {"kind": kind, "ts": ts, "unit_id": unit, "run_id": run}
    rec.update(kw)
    return rec


def _write(path: Path, records) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(r) + "\n" for r in records),
        encoding="utf-8",
    )
    return path


def _source(tmp_path: Path, records, **kw) -> DatabricksSource:
    events = _write(tmp_path / "dbx-events.jsonl", records)
    kw.setdefault("thresholds", TH)
    kw.setdefault("clock", lambda: NOW)
    # HERMETIC BY DEFAULT: dbx_events / dbx_completion are authored by PARALLEL
    # agents and may appear or change on disk mid-run. `None` disables the seam so
    # these assertions measure THIS adapter, not the siblings' current state.
    kw.setdefault("events_mod", None)
    kw.setdefault("completion_mod", None)
    return DatabricksSource(events_path=str(events), **kw)


def _started(unit: str = "u1", run: str = "r1", ts: float = NOW - 10_000) -> list[dict]:
    return [_rec("start", ts, unit, run, attempt_token=f"{run}-t0")]


# ───────────────────────── contract shape ─────────────────────────
def test_source_satisfies_runtime_checkable_protocol(tmp_path):
    src = _source(tmp_path, [])
    assert isinstance(src, MonitorSource)
    assert src.id == "dbxmon"


def test_payload_is_typed_never_flattened(tmp_path):
    src = _source(tmp_path, _started() + [_rec("heartbeat", NOW - 1)])
    snap = src.poll()
    assert isinstance(snap.payload, DbxPayload)
    (unit,) = snap.payload.units
    # the native domain model, NOT a lowest-common-denominator dict
    assert isinstance(unit, DbxUnit)
    assert dataclasses.is_dataclass(unit)
    assert not isinstance(unit, dict)
    # the eight-state vocabulary lives INSIDE the payload, on the unit
    assert isinstance(unit.liveness, Liveness)


def test_no_new_source_state_constants_required(tmp_path):
    """The adapter adds NO SourceState constant — liveness is unit-level, in the payload."""
    assert {s.value for s in SourceState} == {
        "idle",
        "running",
        "done",
        "error",
        "unreachable",
        "stalled",
    }
    # every state this adapter can emit is one of the pre-existing six
    emitted = {
        DatabricksSource._derive_state((), ()),
        DatabricksSource._derive_state((_unit(liveness=Liveness.THINKING),), ()),
        DatabricksSource._derive_state((_unit(liveness=Liveness.STALLED),), ()),
        DatabricksSource._derive_state((_unit(liveness=Liveness.TERMINAL),), ()),
        DatabricksSource._derive_state((_unit(failed=True),), ()),
        _source(tmp_path, []).poll().state,
    }
    assert emitted <= set(SourceState)


def test_liveness_vocabulary_is_the_eight_states():
    assert {m.name for m in Liveness} == {
        "QUEUED",
        "STARTING",
        "THINKING",
        "TOOL_ACTIVE",
        "WAITING_EXTERNAL",
        "HEARTBEAT_LATE",
        "STALLED",
        "TERMINAL",
    }


# ───────────────────────── poll: never raises ─────────────────────────
def test_poll_never_raises_when_event_file_missing(tmp_path):
    """A run that has not written its event file yet is quietly empty, never an error."""
    src = DatabricksSource(
        events_path=str(tmp_path / "does-not-exist.jsonl"),
        thresholds=TH,
        clock=lambda: NOW,
    )
    snap = src.poll()  # must not raise
    assert snap.reachable is True
    assert snap.stale is False
    assert snap.state is SourceState.IDLE
    assert snap.payload == DbxPayload()


def test_poll_never_raises_on_unreadable_locked_file(tmp_path):
    """Two mechanically independent probes of the same never-raise branch."""
    # (1) REAL OSError: open() on a directory (Windows PermissionError /
    #     POSIX IsADirectoryError) — an unmocked I/O failure.
    locked_dir = tmp_path / "events-as-a-dir.jsonl"
    locked_dir.mkdir()
    src = DatabricksSource(
        events_path=str(locked_dir), thresholds=TH, clock=lambda: NOW
    )
    snap = src.poll()  # must not raise
    assert snap.reachable is False
    assert snap.stale is True
    assert snap.state is SourceState.UNREACHABLE
    assert snap.error

    # (2) the true share-lock shape, injected (Windows raises PermissionError on a
    #     file held with an exclusive lock by another process).
    def _locked():
        raise PermissionError("[Errno 13] file is locked by another process")
        yield  # pragma: no cover -- generator marker, never reached

    src2 = DatabricksSource(reader=_locked, thresholds=TH, clock=lambda: NOW)
    snap2 = src2.poll()  # must not raise
    assert snap2.reachable is False and snap2.stale is True
    assert "locked" in (snap2.error or "")


def test_poll_never_raises_on_simulated_api_failure_returns_unreachable_stale(tmp_path):
    """A failing lifecycle API degrades ONE row: unreachable + the last-good payload."""
    boom = {"n": 0}

    def api() -> dict[str, str]:
        boom["n"] += 1
        if boom["n"] > 1:  # first poll succeeds, second fails
            raise RuntimeError(f"databricks 500 {SK_TOKEN}")
        return {}

    src = _source(
        tmp_path,
        _started() + [_rec("heartbeat", NOW - 1)],
        api=api,
    )
    good = src.poll()
    assert good.reachable is True and good.payload.units

    bad = src.poll()  # must not raise
    assert bad.reachable is False
    assert bad.stale is True
    assert bad.state is SourceState.UNREACHABLE
    assert bad.payload is good.payload  # last-good RETAINED, not rebuilt
    assert SK_TOKEN in (bad.error or "")  # raw error kept for logs
    assert SK_TOKEN not in bad.headline  # but the headline is redaction-safe


def test_poll_failure_without_history_returns_empty_payload(tmp_path):
    def api() -> dict[str, str]:
        raise RuntimeError("no cluster")

    src = _source(tmp_path, _started(), api=api)
    snap = src.poll()
    assert snap.reachable is False
    assert snap.payload == DbxPayload()


def test_poll_lets_base_exception_propagate(tmp_path):
    def ctrl_c():
        raise KeyboardInterrupt
        yield  # pragma: no cover -- generator marker, never reached

    src = DatabricksSource(reader=ctrl_c, thresholds=TH, clock=lambda: NOW)
    with pytest.raises(KeyboardInterrupt):
        src.poll()


def test_api_probe_overrides_lifecycle_status(tmp_path):
    """The injected lifecycle probe is authoritative over the event stream."""
    src = _source(
        tmp_path,
        _started() + [_rec("heartbeat", NOW - 1)],
        api=lambda: {"r1/u1": "TERMINATED"},
    )
    snap = src.poll()
    (unit,) = snap.payload.units
    assert unit.task_status == "TERMINATED"
    assert unit.liveness is Liveness.TERMINAL


# ───────────────────────── eight-state liveness discriminator ─────────────────────────
def test_queued_before_start():
    assert derive_liveness(_unit(started_ts=0.0, task_status="PENDING"), NOW, TH) is (
        Liveness.QUEUED
    )
    # lifecycle status is authoritative even once a start row exists
    assert (
        derive_liveness(_unit(started_ts=NOW - 5, task_status="PENDING"), NOW, TH)
        is Liveness.QUEUED
    )


def test_starting_within_grace():
    """Started, nothing has arrived yet, still inside the grace window."""
    fresh = _unit(started_ts=NOW - 5, last_event_ts=0.0, heartbeat_ts=0.0)
    assert derive_liveness(fresh, NOW, TH) is Liveness.STARTING
    # past the grace with STILL zero arrivals, started_ts becomes the liveness clock
    assert derive_liveness(fresh, NOW + 400, TH) is Liveness.STALLED


def test_stale_heartbeat_becomes_heartbeat_late_then_stalled():
    """The mandated progression, walked on ONE unit by advancing the clock only."""
    unit = _unit(last_event_ts=NOW - 100, heartbeat_ts=NOW - 100)
    assert derive_liveness(unit, NOW - 50, TH) is Liveness.THINKING  # idle 50s
    assert derive_liveness(unit, NOW, TH) is Liveness.HEARTBEAT_LATE  # idle 100s > 90
    assert derive_liveness(unit, NOW + 250, TH) is Liveness.STALLED  # idle 350s > 300


def test_thinking_while_transcript_silent_but_tool_active_is_not_stalled(tmp_path):
    """THE cardinal discriminator test: silence alone must NEVER mean STALLED."""
    # (1) the pure discriminator: transcript and heartbeat silent for 10_000s
    silent_but_working = _unit(tool_active=True)
    verdict = derive_liveness(silent_but_working, NOW, TH)
    assert verdict is not Liveness.STALLED
    assert verdict is Liveness.TOOL_ACTIVE

    # (2) end-to-end through a real event file: tool_start with no tool_end
    src = _source(
        tmp_path,
        _started() + [_rec("tool_start", NOW - 10_000, tool="dbx_sql_exec")],
    )
    snap = src.poll()
    (unit,) = snap.payload.units
    assert unit.tool_active is True
    assert unit.liveness is Liveness.TOOL_ACTIVE
    assert unit.liveness is not Liveness.STALLED
    assert snap.state is SourceState.RUNNING
    assert snap.state is not SourceState.STALLED


def test_true_stalled_requires_silence_stale_heartbeat_and_no_active_task():
    """A mini truth-table: each guard is INDEPENDENTLY sufficient to block STALLED."""
    stalled = _unit()  # silent 10_000s, no tool, no remote task, RUNNING
    assert derive_liveness(stalled, NOW, TH) is Liveness.STALLED

    assert derive_liveness(_unit(tool_active=True), NOW, TH) is not Liveness.STALLED
    assert (
        derive_liveness(_unit(remote_task_active=True), NOW, TH) is not Liveness.STALLED
    )
    assert derive_liveness(_unit(heartbeat_ts=NOW - 1), NOW, TH) is not Liveness.STALLED
    assert (
        derive_liveness(_unit(last_event_ts=NOW - 1), NOW, TH) is not Liveness.STALLED
    )
    assert (
        derive_liveness(_unit(task_status="TERMINATED"), NOW, TH)
        is not Liveness.STALLED
    )


def test_waiting_external_while_remote_task_running():
    unit = _unit(remote_task_active=True, remote_task_id="run-4711")
    assert derive_liveness(unit, NOW, TH) is Liveness.WAITING_EXTERNAL
    assert derive_liveness(unit, NOW + 100_000, TH) is Liveness.WAITING_EXTERNAL


def test_terminal_on_terminal_event(tmp_path):
    src = _source(tmp_path, _started() + [_rec("done", NOW - 30)])
    snap = src.poll()
    (unit,) = snap.payload.units
    assert unit.liveness is Liveness.TERMINAL
    assert snap.state is SourceState.DONE


def test_artifact_growth_prevents_stalled_despite_silence():
    """Artifact growth is a real arrival channel — isolated by flipping ONLY the bytes."""
    growing = _unit(artifact_bytes=500, prev_artifact_bytes=100, artifact_ts=NOW - 5)
    flat = _unit(artifact_bytes=500, prev_artifact_bytes=500, artifact_ts=NOW - 5)
    assert derive_liveness(growing, NOW, TH) is Liveness.THINKING
    assert derive_liveness(flat, NOW, TH) is Liveness.STALLED


def test_lease_renewal_counts_as_liveness_arrival():
    renewed = _unit(lease_held=True, lease_renewed_ts=NOW - 5)
    stale_lease = _unit(lease_held=True, lease_renewed_ts=NOW - 10_000)
    assert derive_liveness(renewed, NOW, TH) is Liveness.THINKING
    # merely HOLDING a lease is not liveness — a dead process keeps its lease
    assert derive_liveness(stale_lease, NOW, TH) is Liveness.STALLED


def test_retry_resets_the_liveness_clock():
    retried = _unit(retries=2, last_retry_ts=NOW - 5)
    assert derive_liveness(retried, NOW, TH) is Liveness.THINKING
    assert derive_liveness(_unit(retries=2, last_retry_ts=NOW - 10_000), NOW, TH) is (
        Liveness.STALLED
    )


def test_thresholds_are_configurable_not_hardcoded(tmp_path):
    """ONE unit, three verdicts, differing ONLY by the injected thresholds."""
    unit = _unit(last_event_ts=NOW - 120, heartbeat_ts=NOW - 120)  # idle 120s
    assert derive_liveness(unit, NOW, TH) is Liveness.HEARTBEAT_LATE
    patient = LivenessThresholds(heartbeat_late_s=600.0, stalled_s=1200.0)
    assert derive_liveness(unit, NOW, patient) is Liveness.THINKING
    impatient = LivenessThresholds(heartbeat_late_s=10.0, stalled_s=60.0)
    assert derive_liveness(unit, NOW, impatient) is Liveness.STALLED

    # and the source actually threads its configured thresholds through poll
    records = _started() + [_rec("heartbeat", NOW - 120)]
    assert (
        _source(tmp_path, records, thresholds=patient).poll().payload.units[0].liveness
        is Liveness.THINKING
    )
    assert (
        _source(tmp_path, records, thresholds=impatient)
        .poll()
        .payload.units[0]
        .liveness
        is Liveness.STALLED
    )


def test_liveness_never_uses_cumulative_cpu(tmp_path):
    """HARD RULE: cumulative CPU inverts the answer for a blocked process.

    Two probes: (1) structural — no identifier in the module reads a cpu signal;
    (2) behavioural — a huge cpu field in the event stream changes NOTHING.
    """
    # (1) structural: no field and no identifier names a cpu signal
    import monitorcore.databricks_source as mod

    assert not [f for f in dataclasses.fields(DbxUnit) if "cpu" in f.name.lower()]
    module_src = Path(mod.__file__ or "").read_text(encoding="utf-8")
    tree = ast.parse(module_src)
    idents = {n.id.lower() for n in ast.walk(tree) if isinstance(n, ast.Name)} | {
        n.attr.lower() for n in ast.walk(tree) if isinstance(n, ast.Attribute)
    }
    assert not [i for i in idents if "cpu" in i]

    # (2) behavioural: identical streams differing ONLY by a cpu field agree
    quiet = _started() + [_rec("heartbeat", NOW - 10_000, cpu_seconds=0.0)]
    busy_cpu = _started() + [_rec("heartbeat", NOW - 10_000, cpu_seconds=999_999.0)]
    a = _source(tmp_path / "a", quiet).poll().payload.units[0].liveness
    b = _source(tmp_path / "b", busy_cpu).poll().payload.units[0].liveness
    assert a is b is Liveness.STALLED


# ───────────────────────── visibility ─────────────────────────
def test_retry_is_visible_in_payload_and_headline(tmp_path):
    src = _source(
        tmp_path,
        _started()
        + [
            _rec("retry", NOW - 400, reason="cluster preempted"),
            _rec("retry", NOW - 200, reason="cluster preempted"),
            _rec("heartbeat", NOW - 5),
        ],
    )
    snap = src.poll()
    (unit,) = snap.payload.units
    assert unit.retries == 2
    assert unit.last_retry_ts == NOW - 200
    assert "2 retries" in snap.headline
    card = src.export_model(snap).blocks[0]
    assert "retries=2" in card.lead


def test_cancellation_is_visible(tmp_path):
    src = _source(tmp_path, _started() + [_rec("cancel", NOW - 10)])
    snap = src.poll()
    (unit,) = snap.payload.units
    assert unit.cancelled is True
    assert unit.liveness is Liveness.TERMINAL
    assert unit.failed is False  # a cancellation is not a failure
    assert "1 cancelled" in snap.headline
    assert snap.state is SourceState.DONE


# ───────────────────────── durability / separation ─────────────────────────
def test_monitor_restart_midrun_replays_to_same_final_state(tmp_path):
    """A fresh source over the finished file equals a source that watched it live."""
    records = _started() + [
        _rec("heartbeat", NOW - 500),
        _rec("tool_start", NOW - 400, tool="dbx_sql_exec"),
        _rec("tool_end", NOW - 300),
        _rec("artifact", NOW - 250, bytes=4096),
        _rec("retry", NOW - 200),
        _rec("heartbeat", NOW - 100),
    ]
    events = tmp_path / "dbx-events.jsonl"

    hermetic = dict(
        thresholds=TH, clock=lambda: NOW, events_mod=None, completion_mod=None
    )

    # the LIVE watcher: polls mid-run, then again after the rest lands
    _write(events, records[:3])
    live = DatabricksSource(events_path=str(events), **hermetic)  # type: ignore[arg-type]
    live.poll()
    _write(events, records)
    live_final = live.poll()

    # the RESTARTED monitor: a fresh object, one poll over the complete file
    restarted = DatabricksSource(events_path=str(events), **hermetic)  # type: ignore[arg-type]
    replayed = restarted.poll()

    assert replayed.payload.units == live_final.payload.units
    assert replayed.state is live_final.state
    assert replayed.headline == live_final.headline


def test_two_simultaneous_runs_stay_separated(tmp_path):
    """Same unit_id under two run_ids must not merge — keys are (run, unit)."""
    src = _source(
        tmp_path,
        _started("u1", "rA")
        + _started("u1", "rB")
        + [
            _rec("tool_start", NOW - 10_000, "u1", "rA", tool="dbx_sql_exec"),
            _rec("heartbeat", NOW - 10_000, "u1", "rB"),
        ],
    )
    snap = src.poll()
    assert len(snap.payload.units) == 2
    by_run = {u.run_id: u for u in snap.payload.units}
    assert set(by_run) == {"rA", "rB"}
    assert by_run["rA"].liveness is Liveness.TOOL_ACTIVE
    assert by_run["rB"].liveness is Liveness.STALLED
    assert by_run["rA"].key != by_run["rB"].key
    assert snap.payload.runs == ("rA", "rB")


def test_run_id_collision_is_detected(tmp_path):
    """Two distinct runs claiming ONE run_id is a data-integrity fault, not a unit state."""
    src = _source(
        tmp_path,
        [
            _rec("start", NOW - 900, "u1", "r1", attempt_token="alpha"),
            _rec("start", NOW - 100, "u2", "r1", attempt_token="beta"),
            _rec("heartbeat", NOW - 5, "u2", "r1"),
        ],
    )
    snap = src.poll()
    assert snap.payload.collisions
    assert "r1" in snap.payload.collisions[0]
    assert snap.state is SourceState.ERROR
    assert "collision" in snap.headline
    alert = src.alert(snap)
    assert alert is not None and alert.level == "critical"

    # a consistent token across the same run is NOT a collision
    clean = _source(
        tmp_path / "clean",
        [
            _rec("start", NOW - 900, "u1", "r1", attempt_token="alpha"),
            _rec("start", NOW - 100, "u2", "r1", attempt_token="alpha"),
        ],
    )
    assert clean.poll().payload.collisions == ()


def test_slow_consumer_does_not_unbound_memory(tmp_path):
    """Retained state is O(max_units), independent of how many events arrived."""
    records: list[dict] = []
    for i in range(400):
        records += _started(f"u{i:03d}", "r1", ts=NOW - 10_000 + i)
        records.append(_rec("heartbeat", NOW - 10_000 + i, f"u{i:03d}"))
    src = _source(tmp_path, records, max_units=10)
    snap = src.poll()

    assert len(snap.payload.units) == 10
    assert snap.payload.events_seen == 800  # every event WAS consumed
    assert len(src._acc) <= 10  # the accumulator itself is bounded
    # the survivors are the most-recently-active units, not an arbitrary 10
    assert {u.unit_id for u in snap.payload.units} == {
        f"u{i:03d}" for i in range(390, 400)
    }

    # polling a file that doubled in size does NOT double retained state
    _write(tmp_path / "dbx-events.jsonl", records + records)
    snap2 = src.poll()
    assert len(snap2.payload.units) == 10
    assert len(src._acc) <= 10


# ───────────────────────── no decorative spinner ─────────────────────────
def test_busy_indicator_false_when_no_event_arrived_in_window(tmp_path):
    """Busy is a pure function of ARRIVAL — never of a state label."""
    # everything LOOKS active, but nothing has arrived in 10_000s
    dead = _unit(tool_active=True, task_status="RUNNING")
    assert is_busy(dead, NOW, TH) is False
    assert derive_liveness(dead, NOW, TH) is Liveness.TOOL_ACTIVE  # label != spinner

    alive = _unit(heartbeat_ts=NOW - 1)
    assert is_busy(alive, NOW, TH) is True
    # exactly at the window edge is still busy; one second past it is not
    assert is_busy(_unit(heartbeat_ts=NOW - 30), NOW, TH) is True
    assert is_busy(_unit(heartbeat_ts=NOW - 31), NOW, TH) is False

    # and through a real poll: a tool-active unit with no arrivals is NOT busy
    src = _source(tmp_path, _started() + [_rec("tool_start", NOW - 10_000)])
    (unit,) = src.poll().payload.units
    assert unit.liveness is Liveness.TOOL_ACTIVE
    assert unit.busy is False


def test_busy_glyph_is_not_decorative_dead_agent_is_not_busy(tmp_path):
    """The rendered glyph must DIFFER between a live and a dead unit."""
    dead = _unit(busy=False)
    alive = _unit(busy=True)
    assert busy_glyph(dead) != busy_glyph(alive)

    src = _source(tmp_path, _started() + [_rec("tool_start", NOW - 10_000)])
    line = src.render_native(src.poll())
    assert isinstance(line, str)
    assert line.startswith(busy_glyph(dead))
    assert not line.startswith(busy_glyph(alive))
    assert "TOOL_ACTIVE" in line

    live_src = _source(tmp_path / "live", _started() + [_rec("heartbeat", NOW - 1)])
    live_line = live_src.render_native(live_src.poll())
    assert isinstance(live_line, str)
    assert live_line.startswith(busy_glyph(alive))


# ───────────────────────── contract surface ─────────────────────────
def test_derive_state_matrix():
    derive = DatabricksSource._derive_state
    assert derive((), ()) is SourceState.IDLE
    assert derive((_unit(liveness=Liveness.QUEUED),), ()) is SourceState.IDLE
    assert derive((_unit(liveness=Liveness.THINKING),), ()) is SourceState.RUNNING
    assert derive((_unit(liveness=Liveness.TOOL_ACTIVE),), ()) is SourceState.RUNNING
    assert (
        derive((_unit(liveness=Liveness.WAITING_EXTERNAL),), ()) is SourceState.RUNNING
    )
    assert derive((_unit(liveness=Liveness.HEARTBEAT_LATE),), ()) is SourceState.RUNNING
    assert derive((_unit(liveness=Liveness.TERMINAL),), ()) is SourceState.DONE
    # stalled outranks a healthy sibling; a failure outranks everything
    assert (
        derive(
            (_unit(liveness=Liveness.STALLED), _unit(liveness=Liveness.THINKING)), ()
        )
        is SourceState.STALLED
    )
    assert (
        derive((_unit(liveness=Liveness.STALLED), _unit(failed=True)), ())
        is SourceState.ERROR
    )
    assert (
        derive((_unit(liveness=Liveness.THINKING),), ("r1: dup",)) is SourceState.ERROR
    )


def test_render_native_headline_fallback_and_board(tmp_path):
    empty = _source(tmp_path, [])
    snap = empty.poll()
    assert empty.render_native(snap) == snap.headline

    src = _source(
        tmp_path / "two",
        _started("u1") + _started("u2") + [_rec("heartbeat", NOW - 1, "u2")],
    )
    native = src.render_native(src.poll())
    assert isinstance(native, str)
    assert native.count("\n") == 1  # one board line per unit
    assert "u1" in native and "u2" in native


def test_export_model_empty_and_populated(tmp_path):
    empty = _source(tmp_path, [])
    doc = empty.export_model(empty.poll())
    assert doc.title == "dbxmon"
    assert doc.blocks == ()
    assert doc.active is False
    assert (
        doc.generated_at == "2026-07-17T10:10:00+00:00"
    )  # derived from the poll epoch
    # total/done/error/running/idle/tokens are the RENDERER-CANONICAL keys
    # (render_md._rollup_line KeyErrors without them); `stalled` is the dbx extra.
    assert dict(doc.rollup) == {
        "total": 0,
        "done": 0,
        "error": 0,
        "running": 0,
        "idle": 0,
        "tokens": 0,
        "stalled": 0,
    }

    src = _source(
        tmp_path / "busy",
        _started()
        + [
            _rec("tool_start", NOW - 2, tool="dbx_sql_exec"),
            _rec("artifact", NOW - 2, bytes=2048),
        ],
    )
    snap = src.poll()
    doc = src.export_model(snap)
    assert doc.active is True
    (card,) = doc.blocks
    assert card.card is True
    assert card.title == "r1/u1"
    assert card.badge == "TOOL_ACTIVE"
    assert dict(doc.rollup)["running"] == 1
    md = render_md(doc)  # smoke: the shared renderer consumes the mapping
    assert "r1/u1" in md


def test_headline_accessor_passthrough(tmp_path):
    src = _source(tmp_path, [])
    snap = src.poll()
    assert src.headline(snap) == snap.headline


def test_alert_matrix(tmp_path):
    failed = _source(tmp_path, _started() + [_rec("error", NOW - 5, message="boom")])
    err = failed.alert(failed.poll())
    assert err is not None and err.level == "critical"
    assert err.source_id == "dbxmon"

    stalled_src = _source(tmp_path / "stalled", _started())
    warn = stalled_src.alert(stalled_src.poll())
    assert warn is not None and warn.level == "warn"

    healthy = _source(tmp_path / "ok", _started() + [_rec("heartbeat", NOW - 1)])
    assert healthy.alert(healthy.poll()) is None

    unreachable = Snapshot(
        source_id="dbxmon",
        ts=NOW,
        reachable=False,
        stale=True,
        state=SourceState.UNREACHABLE,
        headline="h",
        payload=DbxPayload(),
        error=f"boom {SK_TOKEN}",
    )
    got = healthy.alert(unreachable)
    assert got is not None and got.level == "warn"
    assert SK_TOKEN not in got.detail  # alert detail is re-scrubbed


# ───────────────────────── stream hygiene / full event vocabulary ─────────────────────────
def test_default_events_path_honours_env_override(monkeypatch):
    monkeypatch.setenv("DBX_MONITOR_EVENTS", "/srv/dbx/events.jsonl")
    assert default_events_path() == "/srv/dbx/events.jsonl"
    monkeypatch.delenv("DBX_MONITOR_EVENTS", raising=False)
    assert default_events_path().endswith("events.jsonl")


def test_malformed_blank_and_headless_lines_are_skipped_not_raised(tmp_path):
    """An append-only NDJSON tail carries junk — it must degrade, never raise.

    A half-written final record is NORMAL for a stream being tailed while it grows.
    """
    events = tmp_path / "dbx-events.jsonl"
    events.parent.mkdir(parents=True, exist_ok=True)
    events.write_text(
        "\n"  # blank line
        "   \n"  # whitespace-only line
        "{not json at all\n"  # malformed — a half-written tail record
        "[1, 2, 3]\n"  # valid JSON, but NOT a dict
        + json.dumps(_rec("start", NOW - 10, attempt_token="t0"))
        + "\n"
        + json.dumps({"kind": "heartbeat", "ts": NOW - 1})  # no unit_id
        + "\n"
        + json.dumps(_rec("heartbeat", NOW - 1))
        + "\n",
        encoding="utf-8",
    )
    src = DatabricksSource(
        events_path=str(events),
        thresholds=TH,
        clock=lambda: NOW,
        events_mod=None,
        completion_mod=None,
    )
    snap = src.poll()  # must not raise
    assert snap.reachable is True
    (unit,) = snap.payload.units
    assert unit.liveness is Liveness.THINKING
    # only the three DICT records reached the fold; the junk never got that far
    assert snap.payload.events_seen == 3


def test_full_event_vocabulary_folds(tmp_path):
    src = _source(
        tmp_path,
        [
            _rec("queued", NOW - 900),
            _rec("start", NOW - 800, attempt_token="t0"),
            _rec("event", NOW - 700),
            _rec("lease_renew", NOW - 650),
            _rec("remote_task_start", NOW - 600, task_id="job-77"),
            _rec("a_kind_from_a_future_writer", NOW - 550),  # unknown → ignored
            _rec("heartbeat", NOW - 500),
        ],
    )
    (u,) = src.poll().payload.units
    assert u.task_status == "RUNNING"
    assert u.lease_held is True and u.lease_renewed_ts == NOW - 650
    assert u.remote_task_active is True and u.remote_task_id == "job-77"
    assert u.liveness is Liveness.WAITING_EXTERNAL

    # closing the remote task and releasing the lease flips both back
    closed = _source(
        tmp_path / "closed",
        [
            _rec("start", NOW - 800, attempt_token="t0"),
            _rec("remote_task_start", NOW - 600, task_id="job-77"),
            _rec("remote_task_end", NOW - 500),
            _rec("lease_renew", NOW - 450),
            _rec("lease_release", NOW - 400),
        ],
    )
    (v,) = closed.poll().payload.units
    assert v.remote_task_active is False
    assert v.lease_held is False
    # nothing active and quiet for 450s > stalled_s — now STALLED is legitimate
    assert v.liveness is Liveness.STALLED


def test_collision_requires_a_token_and_is_recorded_once(tmp_path):
    # a start with NO attempt_token cannot be discriminated → never a collision
    untokened = _source(
        tmp_path / "untokened",
        [_rec("start", NOW - 900, "u1", "r1"), _rec("start", NOW - 800, "u2", "r1")],
    )
    assert untokened.poll().payload.collisions == ()

    # the SAME collision observed twice is recorded ONCE (no unbounded growth)
    repeated = _source(
        tmp_path / "repeated",
        [
            _rec("start", NOW - 900, "u1", "r1", attempt_token="alpha"),
            _rec("start", NOW - 800, "u2", "r1", attempt_token="beta"),
            _rec("start", NOW - 700, "u3", "r1", attempt_token="beta"),
        ],
    )
    assert len(repeated.poll().payload.collisions) == 1


# ───────────────────────── sibling-module seam (parallel agents) ─────────────────────────
def test_sibling_modules_are_optional_when_absent(monkeypatch, tmp_path):
    """dbx_events / dbx_completion are written by PARALLEL agents — never required.

    Independent of whether those files exist on disk right now: the import is forced
    to fail, and the adapter must still poll normally on its built-in fallbacks.
    """
    import monitorcore.databricks_source as mod

    def _no_module(name, package=None):
        raise ImportError(f"no module named {name}")

    monkeypatch.setattr(mod.importlib, "import_module", _no_module)
    assert mod._optional("dbx_events") is None
    assert mod._optional("dbx_completion") is None

    src = _source(tmp_path, _started() + [_rec("done", NOW - 5)])
    snap = src.poll()
    assert snap.reachable is True
    assert snap.payload.units[0].liveness is Liveness.TERMINAL


def test_sibling_auto_import_is_the_production_default(tmp_path):
    """Omitting the kwargs takes the AUTO seam — whether or not the siblings exist.

    This is the only test that touches real on-disk sibling state, and it asserts only
    that the auto path POLLS CLEANLY (never that a sibling is present), so it cannot
    flake on the parallel agents' progress.
    """
    events = _write(
        tmp_path / "dbx-events.jsonl", _started() + [_rec("heartbeat", NOW - 1)]
    )
    src = DatabricksSource(events_path=str(events), thresholds=TH, clock=lambda: NOW)
    snap = src.poll()
    assert snap.reachable is True
    assert len(snap.payload.units) == 1


def test_sibling_normalizer_is_used_when_present(tmp_path):
    """When a sibling IS present it is consulted — and its failures never blind us."""
    import types

    events_mod = types.SimpleNamespace(
        normalize=lambda rec: {**rec, "unit_id": rec["unit_id"].upper()}
    )
    completion_mod = types.SimpleNamespace(is_terminal=lambda rec: rec["kind"] == "fin")

    src = _source(
        tmp_path,
        _started() + [_rec("fin", NOW - 5)],
        events_mod=events_mod,
        completion_mod=completion_mod,
    )
    (unit,) = src.poll().payload.units
    assert unit.unit_id == "U1"  # the sibling normalizer ran
    assert unit.liveness is Liveness.TERMINAL  # the sibling terminal-classifier ran

    # a BROKEN sibling degrades to the built-ins instead of tearing the row down
    broken = types.SimpleNamespace(
        normalize=lambda rec: (_ for _ in ()).throw(ValueError("sibling bug"))
    )
    hurt = _source(
        tmp_path / "hurt",
        _started() + [_rec("heartbeat", NOW - 1)],
        events_mod=broken,
    )
    snap = hurt.poll()
    assert snap.reachable is True
    assert snap.payload.units[0].unit_id == "u1"
