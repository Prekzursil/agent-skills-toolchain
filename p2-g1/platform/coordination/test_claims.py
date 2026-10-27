"""Work claims, fingerprints, and both kinds of duplicate-work suppression."""

from __future__ import annotations

from typing import Any

import pytest

from coordination.claims import (
    WORK_IDENTITY_FIELDS,
    Claim,
    ClaimOutcome,
    ClaimState,
    abandon_claim,
    acquire_claim,
    claim_view,
    complete_claim,
    fingerprint,
    release_claim,
)
from coordination.errors import StoreCorrupt
from coordination.session import DEFAULT_HEARTBEAT_TTL, Liveness, register_session
from coordination.simclock import SimClock
from coordination.store import Store

UNIT: dict[str, Any] = {
    "id": "COORD-0001",
    "title": "cosmetic - not part of identity",
    "phase": "9",
    "question_or_target": "does the lease layer serialise writes?",
    "inputs": ["platform/coordination/leases.py"],
    "dependencies": ["COORD-0000"],
    "assigned_model_vendor_role": {
        "vendor": "anthropic",
        "model": "opus",
        "role": "builder",
    },
    "output_path": "platform/coordination/LEASES.json",
    "output_schema": "platform/schema/receipt.schema.json",
    "evidence_requirement": "two mechanically independent probes",
    "tests_required": ["test_leases.py"],
    "reviewer_requirement": "cross-vendor",
    "completion_sentinel": "SUCCESS:COORD-0001",
    "notes": "cosmetic",
}


def _live(store: Store, sid: str, vendor: str = "anthropic"):
    return register_session(
        store,
        vendor=vendor,
        adapter_id="claude-code",
        tool="claude-code",
        session_id=sid,
    )


def _dead(store: Store, sid: str, vendor: str = "anthropic"):
    return register_session(
        store,
        vendor=vendor,
        adapter_id="claude-code",
        tool="claude-code",
        session_id=sid,
        hold_lock=False,
    )


# --------------------------------------------------------------------------- fingerprints


def test_fingerprint_ignores_cosmetic_fields() -> None:
    other = {
        **UNIT,
        "title": "totally different title",
        "notes": "changed",
        "bucket": "B99",
    }
    assert fingerprint(UNIT) == fingerprint(other)


def test_fingerprint_changes_when_the_semantic_core_changes() -> None:
    for field in WORK_IDENTITY_FIELDS:
        mutated = {**UNIT, field: "MUTATED"}
        assert fingerprint(mutated) != fingerprint(UNIT), (
            f"{field} must be identity-bearing"
        )


def test_fingerprint_ignores_the_assigned_vendor() -> None:
    """Same work under another vendor is the SAME work; whether to duplicate is a declaration."""
    other = {
        **UNIT,
        "assigned_model_vendor_role": {"vendor": "openai", "role": "builder"},
    }
    assert fingerprint(other) == fingerprint(UNIT)


def test_fingerprint_covers_the_field_list_itself() -> None:
    """A unit fingerprinted under a different field set must not collide with this one."""
    assert fingerprint(UNIT, ("id",)) != fingerprint(UNIT)


# ---------------------------------------------------------------------------- acquisition


def test_first_claim_is_granted(store: Store) -> None:
    _live(store, "s1")
    result = acquire_claim(store, unit_id="COORD-0001", unit=UNIT, session_id="s1")
    assert result.outcome is ClaimOutcome.GRANTED
    assert result.claim is not None and result.claim.state is ClaimState.ACTIVE
    assert result.sentinel_line.startswith("SUCCESS:claim/COORD-0001")


def test_second_session_is_suppressed_while_the_first_is_live(store: Store) -> None:
    lock1 = _live(store, "s1")[1]
    try:
        _live(store, "s2")[1]
        acquire_claim(store, unit_id="COORD-0001", unit=UNIT, session_id="s1")
        result = acquire_claim(store, unit_id="COORD-0001", unit=UNIT, session_id="s2")
        assert result.outcome is ClaimOutcome.DUPLICATE_SUPPRESSED
        assert result.incumbent_liveness is Liveness.LIVE
        assert "burn a second budget" in result.reason
    finally:
        if lock1:
            lock1.release()


def test_dead_holder_makes_the_claim_recoverable_not_stealable(
    store: Store, clock: SimClock
) -> None:
    """A dead holder's claim is never auto-taken: recovery/handoff must adjudicate."""
    _dead(store, "s1")
    acquire_claim(store, unit_id="COORD-0001", unit=UNIT, session_id="s1")
    clock.advance(DEFAULT_HEARTBEAT_TTL + 1)
    _dead(store, "s2")
    result = acquire_claim(store, unit_id="COORD-0001", unit=UNIT, session_id="s2")
    assert result.outcome is ClaimOutcome.RECOVERABLE
    assert result.incumbent_liveness is Liveness.DEAD


def test_unverified_holder_blocks(store: Store) -> None:
    """Fail closed: no second signal means no reassignment."""
    _dead(store, "s1")
    acquire_claim(store, unit_id="COORD-0001", unit=UNIT, session_id="s1")
    result = acquire_claim(store, unit_id="COORD-0001", unit=UNIT, session_id="s2")
    assert result.outcome is ClaimOutcome.BLOCKED_UNVERIFIED
    assert "one signal is not evidence" in result.reason


def test_completed_claim_reports_already_complete(store: Store) -> None:
    _dead(store, "s1")
    acquire_claim(store, unit_id="COORD-0001", unit=UNIT, session_id="s1")
    complete_claim(store, "COORD-0001", receipt_path="receipt.json")
    result = acquire_claim(store, unit_id="COORD-0001", unit=UNIT, session_id="s2")
    assert result.outcome is ClaimOutcome.ALREADY_COMPLETE
    assert "re-running it is waste" in result.reason


def test_same_unit_id_with_different_work_is_a_loud_mismatch(store: Store) -> None:
    """The unit was REDEFINED under a live claim. Accepting it would silently change the contract."""
    lock = _live(store, "s1")[1]
    try:
        acquire_claim(store, unit_id="COORD-0001", unit=UNIT, session_id="s1")
        redefined = {**UNIT, "question_or_target": "something else entirely"}
        result = acquire_claim(
            store, unit_id="COORD-0001", unit=redefined, session_id="s2"
        )
        assert result.outcome is ClaimOutcome.FINGERPRINT_MISMATCH
        assert "DIFFERENT work definition" in result.reason
    finally:
        if lock:
            lock.release()


def test_released_claim_needs_explicit_takeover(store: Store) -> None:
    _dead(store, "s1")
    acquire_claim(store, unit_id="COORD-0001", unit=UNIT, session_id="s1")
    release_claim(store, "COORD-0001", note="giving up")
    denied = acquire_claim(store, unit_id="COORD-0001", unit=UNIT, session_id="s2")
    assert denied.outcome is ClaimOutcome.RECOVERABLE
    assert "never taken implicitly" in denied.reason
    granted = acquire_claim(
        store, unit_id="COORD-0001", unit=UNIT, session_id="s2", takeover=True
    )
    assert granted.outcome is ClaimOutcome.GRANTED
    assert granted.claim is not None and granted.claim.takeover_seq == 1


def test_takeover_inherits_the_preserved_artifacts(store: Store, tmp_path) -> None:
    artifact = tmp_path / "partial.json"
    artifact.write_text("{}", encoding="utf-8")
    _dead(store, "s1")
    acquire_claim(store, unit_id="COORD-0001", unit=UNIT, session_id="s1")
    abandon_claim(store, "COORD-0001", artifacts=[artifact])
    taken = acquire_claim(
        store, unit_id="COORD-0001", unit=UNIT, session_id="s2", takeover=True
    )
    assert taken.claim is not None
    assert str(artifact) in taken.claim.artifacts
    assert artifact.exists(), "takeover must not destroy the outgoing work"


# ---------------------------------------------------- duplicate work under a DIFFERENT id


def test_same_work_under_a_different_unit_id_is_suppressed(store: Store) -> None:
    """The expensive duplicate, invisible to an id check."""
    lock = _live(store, "s1")[1]
    try:
        _live(store, "s2")
        acquire_claim(store, unit_id="COORD-0001", unit=UNIT, session_id="s1")
        twin = {**UNIT, "id": "COORD-9999"}
        result = acquire_claim(store, unit_id="COORD-9999", unit=twin, session_id="s2")
        assert result.outcome is ClaimOutcome.DUPLICATE_SUPPRESSED
        assert "same work fingerprint" in result.reason
        assert store.read(store.path_for("claims", "COORD-9999")) is None, "rolled back"
    finally:
        if lock:
            lock.release()


def test_declared_duplicate_is_allowed_and_recorded(store: Store) -> None:
    """Intentional cross-vendor duplication is a strategy - but it must be DECLARED."""
    lock = _live(store, "s1")[1]
    try:
        _live(store, "s2", vendor="codex")
        acquire_claim(store, unit_id="COORD-0001", unit=UNIT, session_id="s1")
        twin = {**UNIT, "id": "COORD-9999"}
        result = acquire_claim(
            store,
            unit_id="COORD-9999",
            unit=twin,
            session_id="s2",
            vendor="openai",
            allow_duplicate=True,
            duplicate_reason="deliberate cross-vendor adversarial re-run",
        )
        assert result.outcome is ClaimOutcome.GRANTED
        assert result.claim is not None
        assert result.claim.declared_duplicate_reason
        dups = [
            name for name, _rec in store.iter_records("fingerprints") if ".dup-" in name
        ]
        assert dups, "the declared duplicate must be auditable in the index"
    finally:
        if lock:
            lock.release()


def test_allow_duplicate_without_a_reason_raises(store: Store) -> None:
    _dead(store, "s1")
    with pytest.raises(StoreCorrupt, match="requires a written duplicate_reason"):
        acquire_claim(
            store,
            unit_id="COORD-0001",
            unit=UNIT,
            session_id="s1",
            allow_duplicate=True,
            duplicate_reason="   ",
        )


def test_duplicate_of_a_vacant_claim_is_allowed(store: Store) -> None:
    """Suppression protects live/complete work, not abandoned work."""
    _dead(store, "s1")
    acquire_claim(store, unit_id="COORD-0001", unit=UNIT, session_id="s1")
    abandon_claim(store, "COORD-0001")
    twin = {**UNIT, "id": "COORD-9999"}
    result = acquire_claim(store, unit_id="COORD-9999", unit=twin, session_id="s2")
    assert result.outcome is ClaimOutcome.GRANTED


# ------------------------------------------------------------------------------ lifecycle


def test_transitions_preserve_artifacts_and_record_the_receipt(
    store: Store, tmp_path
) -> None:
    a = tmp_path / "one.json"
    b = tmp_path / "two.json"
    for p in (a, b):
        p.write_text("{}", encoding="utf-8")
    _dead(store, "s1")
    acquire_claim(store, unit_id="COORD-0001", unit=UNIT, session_id="s1")
    release_claim(store, "COORD-0001", artifacts=[a])
    final = complete_claim(store, "COORD-0001", receipt_path="r.json", artifacts=[b])
    assert set(final.artifacts) == {str(a), str(b)}
    assert final.receipt_path == "r.json"
    assert final.state is ClaimState.COMPLETED


def test_transition_on_a_missing_claim_raises(store: Store) -> None:
    with pytest.raises(StoreCorrupt, match="no claim for unit"):
        release_claim(store, "NOPE")


def test_claim_view_returns_none_when_absent(store: Store) -> None:
    assert claim_view(store, "NOPE") is None


def test_claim_view_reports_holder_liveness(store: Store, clock: SimClock) -> None:
    _dead(store, "s1")
    acquire_claim(store, unit_id="COORD-0001", unit=UNIT, session_id="s1")
    clock.advance(DEFAULT_HEARTBEAT_TTL + 1)
    view = claim_view(store, "COORD-0001")
    assert view is not None and view[1] is Liveness.DEAD


def test_claim_with_no_session_row_fails_closed(store: Store) -> None:
    """An orphan claim cannot be proven free, so it is UNVERIFIED rather than reassignable."""
    acquire_claim(store, unit_id="COORD-0001", unit=UNIT, session_id="ghost")
    result = acquire_claim(store, unit_id="COORD-0001", unit=UNIT, session_id="s2")
    assert result.outcome is ClaimOutcome.BLOCKED_UNVERIFIED


def test_corrupt_claim_record_raises(store: Store) -> None:
    store.write_atomic(store.path_for("claims", "COORD-0001"), {"claim_id": "x"})
    with pytest.raises(StoreCorrupt, match="not readable"):
        claim_view(store, "COORD-0001")


def test_claim_round_trips(store: Store) -> None:
    _dead(store, "s1")
    claim = acquire_claim(store, unit_id="COORD-0001", unit=UNIT, session_id="s1").claim
    assert claim is not None
    assert Claim.from_dict(claim.to_dict()) == claim


def test_journal_records_every_grant_and_denial(store: Store) -> None:
    lock = _live(store, "s1")[1]
    try:
        _live(store, "s2")
        acquire_claim(store, unit_id="COORD-0001", unit=UNIT, session_id="s1")
        acquire_claim(store, unit_id="COORD-0001", unit=UNIT, session_id="s2")
        events = [e["event"] for e in store.journal_entries()]
        assert "claim.granted" in events and "claim.denied" in events
    finally:
        if lock:
            lock.release()
