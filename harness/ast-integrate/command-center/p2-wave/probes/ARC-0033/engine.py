"""A5 ledger alert predicates over recorded traces.

Each named silence becomes a FIRE/SILENT verdict over concrete ledger
fields. Stall verdicts use orchestrator tokens (heartbeat_seq,
progress_token, per-unit deadline, terminal records). File mtime is
carried as a decoy and is never read by a stall predicate.
"""
from __future__ import annotations

from typing import Any

HEARTBEAT_GAP = 3.0
FORBIDDEN_STALL_SIGNALS = frozenset(
    {"mtime", "mtime_ns", "mtime_age", "st_mtime", "file_mtime"}
)

# Author-enumerated modes from the catalog question (five named silences).
AUTHOR_MODE_IDS = (
    "FM-MONITOR-DIES",
    "FM-HARVEST-NOOP",
    "FM-HUNG-BLOCKS-BATCH",
    "FM-DUP-CATALOG",
    "FM-PARTIAL-NO-SENTINEL",
)

# Independent reviewer adds the inverse of FC-11313 (sentinel on a partial).
REVIEWER_MODE_ID = "FM-SENTINEL-ON-PARTIAL"


def _events(trace: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [e for e in trace if isinstance(e, dict)]


def _now(trace: list[dict[str, Any]]) -> float:
    ts = [float(e.get("t", 0.0)) for e in _events(trace)]
    return max(ts) if ts else 0.0


def _kind(trace: list[dict[str, Any]], kind: str) -> list[dict[str, Any]]:
    return [e for e in _events(trace) if e.get("kind") == kind]


def fire_monitor_dies(trace: list[dict[str, Any]]) -> bool:
    """FC-11315: monitor heartbeats stop while claimed remote work continues.

    Ledger: monitor.heartbeat.heartbeat_seq AND unit.progress.progress_token.
    FIRE when the last heartbeat is older than HEARTBEAT_GAP, some claimed
    unit is not terminal, and progress advanced after that last heartbeat.
    """
    hbs = _kind(trace, "monitor.heartbeat")
    if not hbs:
        return False
    last = max(hbs, key=lambda e: (float(e.get("t", 0.0)), int(e.get("heartbeat_seq", 0))))
    last_t = float(last.get("t", 0.0))
    monitor_id = last.get("monitor_id")
    claimed = [
        e
        for e in _kind(trace, "unit.claimed")
        if e.get("monitor_id") == monitor_id
    ]
    claimed_ids = {e.get("unit_id") for e in claimed}
    terminals = {e.get("unit_id") for e in _kind(trace, "unit.terminal")}
    live = claimed_ids - terminals
    if not live:
        return False
    if _now(trace) - last_t <= HEARTBEAT_GAP:
        return False
    later_progress = [
        e
        for e in _kind(trace, "unit.progress")
        if e.get("unit_id") in live and float(e.get("t", 0.0)) > last_t
    ]
    return bool(later_progress)


def fire_harvest_noop(trace: list[dict[str, Any]]) -> bool:
    """FC-11319: harvest process exit 0 with empty dest delta.

    Ledger: harvest.attempt.{process_exit_code, delta_files, delta_bytes}.
    Pre-existing dest files are not a harvest (delta, not stock).
    """
    for e in _kind(trace, "harvest.attempt"):
        exit_code = int(e.get("process_exit_code", -1))
        delta_files = int(e.get("delta_files", -1))
        delta_bytes = int(e.get("delta_bytes", -1))
        if exit_code == 0 and delta_files == 0 and delta_bytes == 0:
            return True
    return False


def fire_hung_blocks_batch(trace: list[dict[str, Any]]) -> bool:
    """FC-11317: wait-all barrier, one unit past its per-unit deadline, no TIMEOUT.

    Ledger: batch.open.barrier_mode, unit.claimed.deadline_t, unit.terminal.
    Silence is an open wait-all batch with an overdue unit and no terminal.
    """
    opens = _kind(trace, "batch.open")
    if not opens:
        return False
    closed = {e.get("batch_id") for e in _kind(trace, "batch.close")}
    now = _now(trace)
    terminals = {e.get("unit_id") for e in _kind(trace, "unit.terminal")}
    claimed = _kind(trace, "unit.claimed")
    for batch in opens:
        batch_id = batch.get("batch_id")
        if batch.get("barrier_mode") != "wait-all":
            continue
        if batch_id in closed:
            continue
        members = [e for e in claimed if e.get("batch_id") == batch_id]
        overdue_unterminated = [
            e
            for e in members
            if e.get("unit_id") not in terminals
            and now > float(e.get("deadline_t", 0.0))
        ]
        if overdue_unterminated:
            return True
    return False


def fire_dup_catalog(trace: list[dict[str, Any]]) -> bool:
    """FC-11320: colliding catalog merge with duplicate ids.

    Ledger: catalog.merge.duplicate_ids (non-empty list).
    """
    for e in _kind(trace, "catalog.merge"):
        dups = e.get("duplicate_ids") or []
        if isinstance(dups, list) and len(dups) > 0:
            return True
    return False


def fire_partial_no_sentinel(trace: list[dict[str, Any]]) -> bool:
    """FC-11313: partial artifact bytes with no completion sentinel.

    Ledger: artifact.observe.{bytes, sentinel_present}.
    In-progress with bytes==0 stays silent.
    """
    for e in _kind(trace, "artifact.observe"):
        nbytes = int(e.get("bytes", 0))
        if nbytes > 0 and e.get("sentinel_present") is not True:
            return True
    return False


def fire_sentinel_on_partial(trace: list[dict[str, Any]]) -> bool:
    """Reviewer-added inverse: sentinel present while completion_predicate is false.

    Ledger: artifact.observe.{sentinel_present, completion_predicate}.
    Author list named missing-sentinel-on-partial and missed this direction.
    """
    for e in _kind(trace, "artifact.observe"):
        if e.get("sentinel_present") is True and e.get("completion_predicate") is not True:
            return True
    return False


PREDICATES: dict[str, dict[str, Any]] = {
    "FM-MONITOR-DIES": {
        "id": "FM-MONITOR-DIES",
        "seeded_class": "FC-11315",
        "title": "monitor dies while remote work continues",
        "ledger_record": "monitor.heartbeat.heartbeat_seq",
        "ledger_counter": "monitor_heartbeat_gap_with_live_progress",
        "alert_predicate": (
            "FIRE iff last monitor.heartbeat for monitor_id is older than "
            "HEARTBEAT_GAP AND a claimed unit has unit.progress.progress_token "
            "advancing after that heartbeat AND that unit has no unit.terminal"
        ),
        "signals": ["heartbeat_seq", "progress_token", "unit.terminal", "t"],
        "stall_predicate": True,
        "fn": fire_monitor_dies,
        "author": True,
    },
    "FM-HARVEST-NOOP": {
        "id": "FM-HARVEST-NOOP",
        "seeded_class": "FC-11319",
        "title": "remote harvest silently does nothing",
        "ledger_record": "harvest.attempt.{process_exit_code,delta_files,delta_bytes}",
        "ledger_counter": "silent_noop_harvest",
        "alert_predicate": (
            "FIRE iff harvest.attempt.process_exit_code==0 AND "
            "delta_files==0 AND delta_bytes==0 (dest stock is not a harvest)"
        ),
        "signals": ["process_exit_code", "delta_files", "delta_bytes"],
        "stall_predicate": False,
        "fn": fire_harvest_noop,
        "author": True,
    },
    "FM-HUNG-BLOCKS-BATCH": {
        "id": "FM-HUNG-BLOCKS-BATCH",
        "seeded_class": "FC-11317",
        "title": "one hung unit blocks a batch",
        "ledger_record": "unit.terminal.state=TIMEOUT + batch.open.barrier_mode",
        "ledger_counter": "batch_open_past_per_unit_deadline",
        "alert_predicate": (
            "FIRE iff batch.open.barrier_mode==wait-all AND batch not closed "
            "AND some unit.claimed.deadline_t < now AND that unit has no "
            "unit.terminal"
        ),
        "signals": ["barrier_mode", "deadline_t", "unit.terminal", "t"],
        "stall_predicate": True,
        "fn": fire_hung_blocks_batch,
        "author": True,
    },
    "FM-DUP-CATALOG": {
        "id": "FM-DUP-CATALOG",
        "seeded_class": "FC-11320",
        "title": "duplicate units from colliding catalogs",
        "ledger_record": "catalog.merge.duplicate_ids",
        "ledger_counter": "catalog_id_collisions",
        "alert_predicate": "FIRE iff catalog.merge.duplicate_ids is a non-empty list",
        "signals": ["duplicate_ids"],
        "stall_predicate": False,
        "fn": fire_dup_catalog,
        "author": True,
    },
    "FM-PARTIAL-NO-SENTINEL": {
        "id": "FM-PARTIAL-NO-SENTINEL",
        "seeded_class": "FC-11313",
        "title": "partial artifact without sentinel",
        "ledger_record": "artifact.observe.{bytes,sentinel_present}",
        "ledger_counter": "partial_artifact_without_sentinel",
        "alert_predicate": (
            "FIRE iff artifact.observe.bytes>0 AND sentinel_present is not true"
        ),
        "signals": ["bytes", "sentinel_present"],
        "stall_predicate": False,
        "fn": fire_partial_no_sentinel,
        "author": True,
    },
    "FM-SENTINEL-ON-PARTIAL": {
        "id": "FM-SENTINEL-ON-PARTIAL",
        "seeded_class": "FC-11313-inverse / FC-11314",
        "title": "sentinel present on a partial (completion_predicate false)",
        "ledger_record": "artifact.observe.{sentinel_present,completion_predicate}",
        "ledger_counter": "sentinel_on_incomplete_artifact",
        "alert_predicate": (
            "FIRE iff sentinel_present is true AND completion_predicate is not true"
        ),
        "signals": ["sentinel_present", "completion_predicate"],
        "stall_predicate": False,
        "fn": fire_sentinel_on_partial,
        "author": False,
    },
}


def evaluate(mode_id: str, trace: list[dict[str, Any]]) -> bool:
    spec = PREDICATES[mode_id]
    return bool(spec["fn"](trace))


def both_states_one(
    mode_id: str, bad: list[dict[str, Any]], good: list[dict[str, Any]]
) -> dict[str, Any]:
    fired = evaluate(mode_id, bad)
    silent = not evaluate(mode_id, good)
    return {
        "mode_id": mode_id,
        "fired_on_silent_failure_trace": fired,
        "silent_on_healthy_trace": silent,
        "pass": bool(fired and silent),
    }


def both_states_all(pairs: dict[str, tuple[list[dict[str, Any]], list[dict[str, Any]]]]) -> dict[str, Any]:
    rows = [
        both_states_one(mode_id, bad, good) for mode_id, (bad, good) in pairs.items()
    ]
    return {
        "per_mode": rows,
        "all_pass": all(r["pass"] for r in rows),
        "failed": [r["mode_id"] for r in rows if not r["pass"]],
    }


def stall_signals_ok(spec: dict[str, Any]) -> bool:
    if not spec.get("stall_predicate"):
        return True
    signals = set(spec.get("signals") or [])
    return signals.isdisjoint(FORBIDDEN_STALL_SIGNALS)


def anti_mtime_report() -> dict[str, Any]:
    stall = [s for s in PREDICATES.values() if s.get("stall_predicate")]
    ok = all(stall_signals_ok(s) for s in stall)
    return {
        "stall_predicates": [s["id"] for s in stall],
        "forbidden_signals": sorted(FORBIDDEN_STALL_SIGNALS),
        "signals_by_id": {s["id"]: list(s["signals"]) for s in stall},
        "no_mtime_in_stall_signals": ok,
    }


def mtime_only_stall(trace: list[dict[str, Any]], now: float, max_age: float) -> bool:
    """Mutant stall detector: infers stalled from file mtimes alone.

    A stalled job and a completed job with the same old mtime are
    indistinguishable. This function is the control that must NOT be
    accepted as an A5 stall predicate.
    """
    mtimes = [float(e["mtime"]) for e in _events(trace) if "mtime" in e]
    if not mtimes:
        return False
    newest = max(mtimes)
    return (now - newest) > max_age
