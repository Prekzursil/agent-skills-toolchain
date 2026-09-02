"""Crash recovery: plan is read-only, artifacts survive, UNVERIFIED needs force, twice is a no-op."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from coordination.claims import (
    ClaimState,
    acquire_claim,
    complete_claim,
    record_artifacts,
)
from coordination.handoff import open_offers
from coordination.leases import acquire_lease
from coordination.recovery import (
    ActionKind,
    artifact_digest_report,
    execute_recovery,
    plan_recovery,
)
from coordination.session import DEFAULT_HEARTBEAT_TTL, Liveness, register_session
from coordination.simclock import SimClock
from coordination.store import Store

UNIT: dict[str, Any] = {
    "id": "COORD-0100",
    "phase": "9",
    "question_or_target": "recover a crashed unit",
    "inputs": ["x"],
    "dependencies": [],
    "output_path": "out.json",
    "output_schema": "s.json",
    "evidence_requirement": "two probes",
    "tests_required": ["t"],
    "reviewer_requirement": "cross-vendor",
    "completion_sentinel": "SUCCESS:COORD-0100",
}


def _session(store: Store, sid: str, *, hold: bool):
    return register_session(
        store,
        vendor="anthropic",
        adapter_id="claude-code",
        tool="claude-code",
        session_id=sid,
        hold_lock=hold,
    )


def _crashed_session_with_work(
    store: Store, clock: SimClock, tmp_path: Path, sid: str = "s-crash"
) -> Path:
    """A session that claimed a unit, leased a file, wrote a partial artifact, then died."""
    _session(store, sid, hold=False)
    artifact = tmp_path / "partial-result.json"
    artifact.write_text(
        '{"progress": "half done", "rows": [1, 2, 3]}', encoding="utf-8"
    )
    acquire_claim(store, unit_id=UNIT["id"], unit=UNIT, session_id=sid)
    record_artifacts(store, UNIT["id"], [artifact])
    acquire_lease(store, session_id=sid, paths=["src/mod.py"], root=tmp_path)
    clock.advance(DEFAULT_HEARTBEAT_TTL + 1)
    return artifact


def test_plan_is_read_only(store: Store, clock: SimClock, tmp_path: Path) -> None:
    """Nothing on disk may change while merely PLANNING - the phases are separate for a reason."""
    _crashed_session_with_work(store, clock, tmp_path)
    before = {
        p.relative_to(store.root).as_posix(): p.read_bytes()
        for p in sorted(store.root.rglob("*"))
        if p.is_file()
    }
    plan = plan_recovery(store)
    after = {
        p.relative_to(store.root).as_posix(): p.read_bytes()
        for p in sorted(store.root.rglob("*"))
        if p.is_file()
    }
    assert before == after
    assert not plan.is_empty


def test_dead_session_work_is_planned_automatically(
    store: Store, clock: SimClock, tmp_path: Path
) -> None:
    _crashed_session_with_work(store, clock, tmp_path)
    plan = plan_recovery(store)
    assert plan.dead == ("s-crash",)
    kinds = {a.kind for a in plan.actions}
    assert kinds == {ActionKind.ABANDON_AND_OFFER, ActionKind.RELEASE_LEASES}
    assert plan.forced_actions == ()


def test_execute_preserves_the_artifact_bytes(
    store: Store, clock: SimClock, tmp_path: Path
) -> None:
    """Spec line 10983's second obligation, asserted on the bytes rather than on the list."""
    artifact = _crashed_session_with_work(store, clock, tmp_path)
    digest_before = hashlib.sha256(artifact.read_bytes()).hexdigest()
    outcome = execute_recovery(store, plan_recovery(store))
    assert artifact.exists()
    assert hashlib.sha256(artifact.read_bytes()).hexdigest() == digest_before
    assert outcome.artifacts_missing == ()
    assert outcome.sentinel_line.startswith("SUCCESS:recovery")
    assert "artifacts_preserved=all" in outcome.sentinel_line


def test_execute_abandons_the_claim_and_opens_a_handoff(
    store: Store, clock: SimClock, tmp_path: Path
) -> None:
    artifact = _crashed_session_with_work(store, clock, tmp_path)
    outcome = execute_recovery(store, plan_recovery(store))
    assert outcome.abandoned_claims == (UNIT["id"],)
    raw = store.read(store.path_for("claims", UNIT["id"]))
    assert raw is not None and raw["state"] == ClaimState.ABANDONED.value
    offers = open_offers(store, unit_id=UNIT["id"])
    assert len(offers) == 1
    assert str(artifact) in offers[0].artifacts


def test_execute_releases_the_dead_sessions_leases(
    store: Store, clock: SimClock, tmp_path: Path
) -> None:
    _crashed_session_with_work(store, clock, tmp_path)
    outcome = execute_recovery(store, plan_recovery(store))
    assert len(outcome.released_leases) == 1
    _session(store, "s-new", hold=False)
    assert acquire_lease(
        store, session_id="s-new", paths=["src/mod.py"], root=tmp_path
    ).granted


def test_recovery_is_idempotent_in_actions_and_in_bytes(
    store: Store, clock: SimClock, tmp_path: Path
) -> None:
    """Second run plans nothing, and the record bytes are identical afterwards.

    Journal lines are excluded from the byte comparison: the journal is append-only by design and
    a second run legitimately records that it found nothing to do.
    """
    _crashed_session_with_work(store, clock, tmp_path)
    execute_recovery(store, plan_recovery(store))

    def records() -> dict[str, bytes]:
        return {
            p.relative_to(store.root).as_posix(): p.read_bytes()
            for p in sorted(store.root.rglob("*.json"))
            if p.is_file()
        }

    after_first = records()
    second_plan = plan_recovery(store)
    assert second_plan.is_empty, [a.to_dict() for a in second_plan.actions]
    execute_recovery(store, second_plan)
    assert records() == after_first


def test_unverified_session_is_skipped_without_force(
    store: Store, tmp_path: Path
) -> None:
    """Default is inaction, and the plan says loudly what it declined to do."""
    _session(store, "s-unverified", hold=False)
    acquire_claim(store, unit_id=UNIT["id"], unit=UNIT, session_id="s-unverified")
    plan = plan_recovery(store)
    assert plan.unverified == ("s-unverified",)
    assert len(plan.forced_actions) == len(plan.actions) >= 1
    outcome = execute_recovery(store, plan)
    assert outcome.applied == ()
    assert len(outcome.skipped) == len(plan.actions)
    raw = store.read(store.path_for("claims", UNIT["id"]))
    assert raw is not None and raw["state"] == ClaimState.ACTIVE.value
    assert any(e["event"] == "recovery.skipped" for e in store.journal_entries())


def test_force_applies_the_unverified_actions(store: Store, tmp_path: Path) -> None:
    _session(store, "s-unverified", hold=False)
    acquire_claim(store, unit_id=UNIT["id"], unit=UNIT, session_id="s-unverified")
    outcome = execute_recovery(store, plan_recovery(store), force=True)
    assert outcome.skipped == ()
    assert outcome.abandoned_claims == (UNIT["id"],)


def test_live_session_is_never_touched(store: Store, tmp_path: Path) -> None:
    _, lock = _session(store, "s-live", hold=True)
    try:
        acquire_claim(store, unit_id=UNIT["id"], unit=UNIT, session_id="s-live")
        acquire_lease(store, session_id="s-live", paths=["src/x.py"], root=tmp_path)
        plan = plan_recovery(store)
        assert plan.is_empty
        assert [v.liveness for v in plan.sessions] == [Liveness.LIVE]
    finally:
        if lock:
            lock.release()


def test_completed_claim_of_a_dead_session_is_a_noop_not_a_reopen(
    store: Store, clock: SimClock, tmp_path: Path
) -> None:
    """A finished unit does not become unfinished because its author died."""
    _session(store, "s-done", hold=False)
    acquire_claim(store, unit_id=UNIT["id"], unit=UNIT, session_id="s-done")
    complete_claim(store, UNIT["id"], receipt_path="r.json")
    clock.advance(DEFAULT_HEARTBEAT_TTL + 1)
    plan = plan_recovery(store)
    assert [a.kind for a in plan.actions] == [ActionKind.NOOP_COMPLETED]
    assert "does not un-finish it" in plan.actions[0].reason
    execute_recovery(store, plan)
    raw = store.read(store.path_for("claims", UNIT["id"]))
    assert raw is not None and raw["state"] == ClaimState.COMPLETED.value
    assert open_offers(store) == ()


def test_gracefully_closed_session_with_unfinished_work_is_recovered(
    store: Store, clock: SimClock, tmp_path: Path
) -> None:
    from coordination.session import close_session

    _session(store, "s-closed", hold=False)
    acquire_claim(store, unit_id=UNIT["id"], unit=UNIT, session_id="s-closed")
    close_session(store, "s-closed")
    plan = plan_recovery(store)
    assert plan.forced_actions == (), "a graceful close is definitive; no force needed"
    assert [a.kind for a in plan.actions] == [ActionKind.ABANDON_AND_OFFER]


def test_missing_artifact_is_reported_loudly_not_dropped(
    store: Store, clock: SimClock, tmp_path: Path
) -> None:
    artifact = _crashed_session_with_work(store, clock, tmp_path)
    artifact.unlink()
    outcome = execute_recovery(store, plan_recovery(store))
    assert outcome.artifacts_missing == (str(artifact),)
    assert outcome.sentinel_line.startswith("FAILED:recovery")
    offers = open_offers(store, unit_id=UNIT["id"])
    assert str(artifact) in offers[0].artifacts, "the path stays on the record"


def test_required_capabilities_flow_into_the_offer(
    store: Store, clock: SimClock, tmp_path: Path
) -> None:
    _crashed_session_with_work(store, clock, tmp_path)
    plan = plan_recovery(store, required_capabilities=["fs.write", "proc.exec"])
    outcome = execute_recovery(store, plan)
    assert outcome.offers[0].required_capabilities == ("fs.write", "proc.exec")


def test_plan_serialises_with_both_signals_per_session(
    store: Store, clock: SimClock, tmp_path: Path
) -> None:
    _crashed_session_with_work(store, clock, tmp_path)
    payload = plan_recovery(store).to_dict()
    assert payload["kind"] == "recovery_plan"
    assert payload["sessions"][0]["signals"]["B_oslock"]["outcome"] == "FREE"
    assert payload["automatic"] >= 1


def test_artifact_digest_report_records_sizes_not_content_hashes(
    tmp_path: Path,
) -> None:
    """Never hash working-tree bytes: git stores LF, Windows checks out CRLF."""
    present = tmp_path / "a.json"
    present.write_text('{"a": 1}', encoding="utf-8")
    report = artifact_digest_report([present, tmp_path / "gone.json"])
    assert report["checked"] == 2 and report["present"] == 1
    assert report["missing"] == [str(tmp_path / "gone.json")]
    assert "no working-tree byte hashing" in report["note"]
    assert not any("sha" in str(k).lower() for k in report)
