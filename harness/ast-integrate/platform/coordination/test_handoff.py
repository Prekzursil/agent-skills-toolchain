"""Handoff: re-negotiate at accept time, degrade loudly, and preserve the artifact bytes."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest
import vendor_identity

from coordination.adapters import load_adapter_registry
from coordination.capability import NegotiationVerdict
from coordination.claims import (
    ClaimState,
    acquire_claim,
    complete_claim,
    record_artifacts,
)
from coordination.errors import HandoffRefused, StoreCorrupt
from coordination.handoff import (
    OfferState,
    accept_handoff,
    decline_handoff,
    inspect_artifacts,
    offer_handoff,
    open_offers,
)
from coordination.session import DEFAULT_HEARTBEAT_TTL, register_session
from coordination.simclock import SimClock
from coordination.store import Store

UNIT: dict[str, Any] = {
    "id": "COORD-0200",
    "phase": "9",
    "question_or_target": "hand this unit over",
    "inputs": ["i"],
    "dependencies": [],
    "output_path": "o.json",
    "output_schema": "s.json",
    "evidence_requirement": "two probes",
    "tests_required": ["t"],
    "reviewer_requirement": "cross-vendor",
    "completion_sentinel": "SUCCESS:COORD-0200",
}


def _registry():
    return load_adapter_registry()


def _crashed_holder(store: Store, clock: SimClock, tmp_path: Path) -> Path:
    register_session(
        store,
        vendor="anthropic",
        adapter_id="claude-code",
        tool="claude-code",
        session_id="s-gone",
        hold_lock=False,
    )
    artifact = tmp_path / "half.json"
    artifact.write_text('{"rows": [1, 2, 3], "state": "half"}', encoding="utf-8")
    acquire_claim(
        store,
        unit_id=UNIT["id"],
        unit=UNIT,
        session_id="s-gone",
        adapter_id="claude-code",
        vendor="anthropic",
    )
    record_artifacts(store, UNIT["id"], [artifact])
    clock.advance(DEFAULT_HEARTBEAT_TTL + 1)
    return artifact


def test_offer_carries_the_fingerprint_and_artifacts(
    store: Store, clock: SimClock, tmp_path: Path
) -> None:
    artifact = _crashed_holder(store, clock, tmp_path)
    offer = offer_handoff(store, unit_id=UNIT["id"], reason="holder died")
    assert offer.state is OfferState.OPEN
    assert offer.from_session == "s-gone"
    assert str(artifact) in offer.artifacts
    assert offer.fingerprint


def test_offer_on_a_completed_unit_is_refused(
    store: Store, clock: SimClock, tmp_path: Path
) -> None:
    _crashed_holder(store, clock, tmp_path)
    complete_claim(store, UNIT["id"], receipt_path="r.json")
    with pytest.raises(StoreCorrupt, match="re-open a closed unit"):
        offer_handoff(store, unit_id=UNIT["id"], reason="why")


def test_offer_without_a_claim_raises(store: Store) -> None:
    with pytest.raises(StoreCorrupt, match="no claim record"):
        offer_handoff(store, unit_id="NOPE", reason="x")


def test_accept_transfers_the_claim_and_preserves_bytes(
    store: Store, clock: SimClock, tmp_path: Path
) -> None:
    """The obligation an exception handler drops: the artifact must still be there, unchanged."""
    artifact = _crashed_holder(store, clock, tmp_path)
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    offer = offer_handoff(
        store,
        unit_id=UNIT["id"],
        reason="crash",
        required_capabilities=["fs.read", "fs.write"],
    )
    register_session(
        store,
        vendor="codex",
        adapter_id="codex-cli",
        tool="codex-cli",
        session_id="s-new",
        hold_lock=False,
    )
    result = accept_handoff(
        store,
        offer_id=offer.offer_id,
        session_id="s-new",
        adapter=_registry().get("codex-cli"),
        unit=UNIT,
    )
    assert result.claim.session_id == "s-new"
    assert result.claim.state is ClaimState.ACTIVE
    assert str(artifact) in result.claim.artifacts
    assert artifact.exists()
    assert hashlib.sha256(artifact.read_bytes()).hexdigest() == digest
    assert result.clean is True
    assert result.sentinel_line.startswith("SUCCESS:handoff/COORD-0200")


def test_accept_records_the_vendor_change_canonically(
    store: Store, clock: SimClock, tmp_path: Path
) -> None:
    """A unit changing hands mid-flight can invalidate a review that WAS cross-vendor."""
    _crashed_holder(store, clock, tmp_path)
    offer = offer_handoff(store, unit_id=UNIT["id"], reason="crash")
    result = accept_handoff(
        store,
        offer_id=offer.offer_id,
        session_id="s-new",
        adapter=_registry().get("codex-cli"),
        unit=UNIT,
    )
    assert result.vendor_comparison == vendor_identity.Comparison.CROSS_VENDOR.value
    assert "openai" in result.vendor_reason


def test_same_vendor_handoff_is_recorded_as_same_vendor(
    store: Store, clock: SimClock, tmp_path: Path
) -> None:
    _crashed_holder(store, clock, tmp_path)
    offer = offer_handoff(store, unit_id=UNIT["id"], reason="crash")
    result = accept_handoff(
        store,
        offer_id=offer.offer_id,
        session_id="s-new",
        adapter=_registry().get("claude-code"),
        unit=UNIT,
    )
    assert result.vendor_comparison == vendor_identity.Comparison.SAME_VENDOR.value


def test_refused_when_the_receiver_cannot_satisfy_a_required_capability(
    store: Store, clock: SimClock, tmp_path: Path
) -> None:
    """The interchangeability lie, refused. The offer stays OPEN and nothing is reassigned."""
    artifact = _crashed_holder(store, clock, tmp_path)
    offer = offer_handoff(
        store,
        unit_id=UNIT["id"],
        reason="crash",
        required_capabilities=["interactive.owner_approval"],
    )
    with pytest.raises(HandoffRefused) as exc:
        accept_handoff(
            store,
            offer_id=offer.offer_id,
            session_id="s-codex",
            adapter=_registry().get("codex-cli"),
            unit=UNIT,
        )
    assert exc.value.missing == ("interactive.owner_approval",)
    assert exc.value.offer_id == offer.offer_id
    assert open_offers(store, unit_id=UNIT["id"])[0].state is OfferState.OPEN
    assert artifact.exists(), "a refusal must not touch the artifact"
    raw = store.read(store.path_for("claims", UNIT["id"]))
    assert raw is not None and raw["session_id"] == "s-gone", "nothing reassigned"


def test_unmeasured_adapter_is_refused_not_trusted(
    store: Store, clock: SimClock, tmp_path: Path
) -> None:
    _crashed_holder(store, clock, tmp_path)
    offer = offer_handoff(
        store, unit_id=UNIT["id"], reason="crash", required_capabilities=["fs.write"]
    )
    with pytest.raises(HandoffRefused, match="missing"):
        accept_handoff(
            store,
            offer_id=offer.offer_id,
            session_id="s-gemini",
            adapter=_registry().get("gemini-cli"),
            unit=UNIT,
        )


def test_degraded_handoff_is_accepted_but_never_recorded_as_clean(
    store: Store, clock: SimClock, tmp_path: Path
) -> None:
    """DEGRADED proceeds AND names what was lost. That is the whole 'degrade loudly' contract."""
    _crashed_holder(store, clock, tmp_path)
    offer = offer_handoff(
        store,
        unit_id=UNIT["id"],
        reason="crash",
        required_capabilities=["fs.write", "sandbox.enforced"],
    )
    result = accept_handoff(
        store,
        offer_id=offer.offer_id,
        session_id="s-new",
        adapter=_registry().get("codex-cli"),
        unit=UNIT,
    )
    assert result.negotiation.verdict is NegotiationVerdict.DEGRADED
    assert result.degraded_capabilities == ("sandbox.enforced",)
    assert result.clean is False
    assert result.sentinel_line.startswith("FAILED:handoff/")
    entry = next(e for e in store.journal_entries() if e["event"] == "handoff.accepted")
    assert entry["degraded"] == ["sandbox.enforced"]
    assert entry["clean"] is False


def test_missing_artifact_makes_the_handoff_unclean(
    store: Store, clock: SimClock, tmp_path: Path
) -> None:
    artifact = _crashed_holder(store, clock, tmp_path)
    offer = offer_handoff(store, unit_id=UNIT["id"], reason="crash")
    artifact.unlink()
    result = accept_handoff(
        store,
        offer_id=offer.offer_id,
        session_id="s-new",
        adapter=_registry().get("claude-code"),
        unit=UNIT,
    )
    assert result.missing_artifacts == (str(artifact),)
    assert result.clean is False


def test_accepting_a_handoff_with_a_different_work_definition_is_blocked(
    store: Store, clock: SimClock, tmp_path: Path
) -> None:
    """A near-enough handoff is not a handoff: the fingerprint must match, and nothing mutates.

    Ordering matters as much as the check. If the outgoing claim were vacated before the
    definition was validated, a refused handoff would leave the unit unowned.
    """
    _crashed_holder(store, clock, tmp_path)
    offer = offer_handoff(store, unit_id=UNIT["id"], reason="crash")
    before = store.read(store.path_for("claims", UNIT["id"]))
    with pytest.raises(HandoffRefused, match="does not match the offer"):
        accept_handoff(
            store,
            offer_id=offer.offer_id,
            session_id="s-new",
            adapter=_registry().get("claude-code"),
            unit={**UNIT, "question_or_target": "a completely different question"},
        )
    assert store.read(store.path_for("claims", UNIT["id"])) == before
    assert open_offers(store, unit_id=UNIT["id"])[0].state is OfferState.OPEN


def test_takeover_of_a_vacant_claim_still_enforces_the_fingerprint(
    store: Store, clock: SimClock, tmp_path: Path
) -> None:
    """``takeover=True`` does not waive FINGERPRINT-MISMATCH.

    Inheriting an abandoned claim's artifacts under a different work definition would attach one
    unit's work product to another unit's contract - the data-corrupting direction.
    """
    from coordination.claims import ClaimOutcome, abandon_claim

    _crashed_holder(store, clock, tmp_path)
    abandon_claim(store, UNIT["id"])
    result = acquire_claim(
        store,
        unit_id=UNIT["id"],
        unit={**UNIT, "output_path": "somewhere-else.json"},
        session_id="s-new",
        takeover=True,
    )
    assert result.outcome is ClaimOutcome.FINGERPRINT_MISMATCH
    assert "a takeover does not waive this" in result.reason


def test_voluntary_handoff_from_a_live_holder_is_recorded_as_handed_off(
    store: Store, clock: SimClock, tmp_path: Path
) -> None:
    """A live session can hand its own work over; the outgoing claim says HANDED-OFF, not ABANDONED.

    Two different histories: abandoned means nobody has it, handed-off means somebody specific
    took it. Collapsing them would erase who the work went to.
    """
    _, lock = register_session(
        store,
        vendor="anthropic",
        adapter_id="claude-code",
        tool="claude-code",
        session_id="s-busy",
    )
    try:
        acquire_claim(store, unit_id=UNIT["id"], unit=UNIT, session_id="s-busy")
        offer = offer_handoff(store, unit_id=UNIT["id"], reason="rebalancing the queue")
        result = accept_handoff(
            store,
            offer_id=offer.offer_id,
            session_id="s-fresh",
            adapter=_registry().get("codex-cli"),
            unit=UNIT,
        )
        assert result.claim.session_id == "s-fresh"
        events = [e["event"] for e in store.journal_entries()]
        assert "claim.transition" in events
        assert any(
            e.get("state") == ClaimState.HANDED_OFF.value
            for e in store.journal_entries()
            if e["event"] == "claim.transition"
        )
    finally:
        if lock:
            lock.release()


def test_stale_offer_is_refused_after_the_unit_moved_on(
    store: Store, clock: SimClock, tmp_path: Path
) -> None:
    _crashed_holder(store, clock, tmp_path)
    offer = offer_handoff(store, unit_id=UNIT["id"], reason="crash")
    accept_handoff(
        store,
        offer_id=offer.offer_id,
        session_id="s-first",
        adapter=_registry().get("claude-code"),
        unit=UNIT,
    )
    second = offer_handoff(store, unit_id=UNIT["id"], reason="again")
    store.write_atomic(
        store.path_for("handoffs", second.offer_id),
        {**second.to_dict(), "from_session": "somebody-else"},
    )
    with pytest.raises(HandoffRefused, match="stale offer"):
        accept_handoff(
            store,
            offer_id=second.offer_id,
            session_id="s-third",
            adapter=_registry().get("claude-code"),
            unit=UNIT,
        )


def test_an_offer_cannot_be_accepted_twice(
    store: Store, clock: SimClock, tmp_path: Path
) -> None:
    _crashed_holder(store, clock, tmp_path)
    offer = offer_handoff(store, unit_id=UNIT["id"], reason="crash")
    accept_handoff(
        store,
        offer_id=offer.offer_id,
        session_id="s-new",
        adapter=_registry().get("claude-code"),
        unit=UNIT,
    )
    with pytest.raises(StoreCorrupt, match="cannot be accepted twice"):
        accept_handoff(
            store,
            offer_id=offer.offer_id,
            session_id="s-third",
            adapter=_registry().get("claude-code"),
            unit=UNIT,
        )


def test_decline_leaves_the_offer_open_for_others(
    store: Store, clock: SimClock, tmp_path: Path
) -> None:
    """One adapter's inability is not the unit's death."""
    _crashed_holder(store, clock, tmp_path)
    offer = offer_handoff(store, unit_id=UNIT["id"], reason="crash")
    decline_handoff(store, offer.offer_id, reason="busy")
    assert open_offers(store, unit_id=UNIT["id"])[0].offer_id == offer.offer_id
    assert any(e["event"] == "handoff.declined" for e in store.journal_entries())


def test_decline_of_unknown_offer_raises(store: Store) -> None:
    with pytest.raises(StoreCorrupt, match="no handoff offer"):
        decline_handoff(store, "handoff-nope", reason="x")


def test_inspect_artifacts_reports_present_and_missing_with_sizes(
    tmp_path: Path,
) -> None:
    present = tmp_path / "a.json"
    present.write_text('{"a": 1}', encoding="utf-8")
    status = inspect_artifacts([present, tmp_path / "gone.json"])
    assert status[0].present and status[0].size_bytes == len('{"a": 1}')
    assert status[1].present is False and status[1].size_bytes is None


def test_inspect_artifacts_does_not_create_anything(tmp_path: Path) -> None:
    inspect_artifacts([tmp_path / "never.json"])
    assert list(tmp_path.iterdir()) == []


def test_handoff_result_serialises_with_the_negotiation(
    store: Store, clock: SimClock, tmp_path: Path
) -> None:
    _crashed_holder(store, clock, tmp_path)
    offer = offer_handoff(
        store, unit_id=UNIT["id"], reason="crash", required_capabilities=["fs.read"]
    )
    payload = accept_handoff(
        store,
        offer_id=offer.offer_id,
        session_id="s-new",
        adapter=_registry().get("claude-code"),
        unit=UNIT,
    ).to_dict()
    assert payload["kind"] == "handoff_result"
    assert payload["negotiation"]["verdict"] == "AGREED"
    assert payload["vendor_comparison"] in {
        "SAME-VENDOR",
        "CROSS-VENDOR",
        "NOT-COMPUTABLE",
    }
