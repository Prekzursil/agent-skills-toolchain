"""Handoff: moving an unfinished work unit to another session, possibly another vendor.

THE OBLIGATION THAT IS EASY TO DROP

Spec line 10983 is two obligations in one sentence: *"Degrade loudly AND preserve the work
artifact."* An exception handler naturally satisfies the first and quietly drops the second. So
every handoff here:

  * carries the outgoing claim's artifact list onto the incoming claim, and
  * STATS each artifact and records PRESENT/MISSING per path.

A missing artifact is recorded, never silently removed from the list, and no code path in this
module deletes, moves, or truncates a file. ``test_handoff.py`` asserts the artifact files still
exist byte-for-byte after a handoff from a crashed session.

CAPABILITY RE-NEGOTIATION IS MANDATORY AT ACCEPT TIME

A handoff is the exact moment where "pretend full interchangeability" is tempting: the work is
half-done, someone is available, ship it. So accepting re-negotiates the unit's required
capabilities against the RECEIVING adapter:

  AGREED   -> accepted
  DEGRADED -> accepted, and the lost capabilities are named on the handoff record and in the
              journal. A degraded handoff is never recorded as a clean one.
  REFUSED  -> :class:`HandoffRefused` with the missing capability ids. The offer stays OPEN so
              another session can take it; nothing is silently reassigned.

THE VENDOR CHANGE IS RECORDED, NOT ASSUMED HARMLESS (leak L-09)

``vendor_identity.compare`` (canonical, three-valued) classifies the transfer as SAME-VENDOR,
CROSS-VENDOR or NOT-COMPUTABLE. This matters downstream: predicate condition 9 requires an
independent reviewer of a DIFFERENT vendor, and a unit that changes hands mid-flight can silently
invalidate a review that was cross-vendor before the move. The comparison is recorded so the
reducer's later verdict is explainable rather than surprising.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from . import _libpath  # noqa: F401  - side effect: platform/lib on sys.path
from .adapters import VendorAdapter
from .capability import Negotiation, NegotiationVerdict
from .claims import Claim, ClaimState, acquire_claim, mark_handed_off
from .claims import fingerprint as claim_fingerprint
from .errors import HandoffRefused, StoreCorrupt
from .store import Store

import vendor_identity  # noqa: E402  - resolved by _libpath above

__all__ = [
    "ArtifactStatus",
    "HandoffOffer",
    "HandoffResult",
    "OfferState",
    "accept_handoff",
    "decline_handoff",
    "inspect_artifacts",
    "offer_handoff",
    "open_offers",
]


class OfferState(str, Enum):
    OPEN = "OPEN"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"
    WITHDRAWN = "WITHDRAWN"


@dataclass(frozen=True)
class ArtifactStatus:
    """One artifact's fate across the handoff. ``size_bytes`` is None when absent."""

    path: str
    present: bool
    size_bytes: int | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "present": self.present,
            "size_bytes": self.size_bytes,
        }


def inspect_artifacts(paths: Iterable[str | Path]) -> tuple[ArtifactStatus, ...]:
    """Stat each artifact. Read-only: nothing here writes, moves, or removes a file."""
    out: list[ArtifactStatus] = []
    for raw in paths:
        p = Path(raw)
        try:
            size = p.stat().st_size
        except OSError:
            out.append(ArtifactStatus(str(p), False, None))
        else:
            out.append(ArtifactStatus(str(p), True, size))
    return tuple(out)


@dataclass(frozen=True)
class HandoffOffer:
    offer_id: str
    unit_id: str
    fingerprint: str
    from_session: str
    from_adapter: str
    from_vendor: str
    reason: str
    created_at: float
    artifacts: tuple[str, ...] = ()
    receipt_path: str | None = None
    required_capabilities: tuple[str, ...] = ()
    state: OfferState = OfferState.OPEN
    accepted_by: str | None = None
    accepted_at: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "handoff_offer",
            "offer_id": self.offer_id,
            "unit_id": self.unit_id,
            "fingerprint": self.fingerprint,
            "from_session": self.from_session,
            "from_adapter": self.from_adapter,
            "from_vendor": self.from_vendor,
            "reason": self.reason,
            "created_at": self.created_at,
            "artifacts": list(self.artifacts),
            "receipt_path": self.receipt_path,
            "required_capabilities": list(self.required_capabilities),
            "state": self.state.value,
            "accepted_by": self.accepted_by,
            "accepted_at": self.accepted_at,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> HandoffOffer:
        try:
            return cls(
                offer_id=str(raw["offer_id"]),
                unit_id=str(raw["unit_id"]),
                fingerprint=str(raw["fingerprint"]),
                from_session=str(raw["from_session"]),
                from_adapter=str(raw.get("from_adapter", "")),
                from_vendor=str(raw.get("from_vendor", "")),
                reason=str(raw.get("reason", "")),
                created_at=float(raw.get("created_at", 0.0)),
                artifacts=tuple(str(a) for a in raw.get("artifacts", ())),
                receipt_path=(
                    None
                    if raw.get("receipt_path") is None
                    else str(raw["receipt_path"])
                ),
                required_capabilities=tuple(
                    str(c) for c in raw.get("required_capabilities", ())
                ),
                state=OfferState(raw.get("state", "OPEN")),
                accepted_by=(
                    None if raw.get("accepted_by") is None else str(raw["accepted_by"])
                ),
                accepted_at=(
                    None
                    if raw.get("accepted_at") is None
                    else float(raw["accepted_at"])
                ),
            )
        except (KeyError, ValueError) as exc:
            raise StoreCorrupt(f"handoff offer record is not readable: {exc}") from exc


@dataclass(frozen=True)
class HandoffResult:
    offer: HandoffOffer
    claim: Claim
    negotiation: Negotiation
    artifact_status: tuple[ArtifactStatus, ...]
    vendor_comparison: str
    vendor_reason: str

    @property
    def degraded_capabilities(self) -> tuple[str, ...]:
        return tuple(f.capability for f in self.negotiation.degraded)

    @property
    def missing_artifacts(self) -> tuple[str, ...]:
        return tuple(a.path for a in self.artifact_status if not a.present)

    @property
    def clean(self) -> bool:
        """A handoff is clean only when nothing degraded AND every artifact survived."""
        return (
            self.negotiation.verdict is NegotiationVerdict.AGREED
            and not self.missing_artifacts
        )

    @property
    def sentinel_line(self) -> str:
        if self.clean:
            return (
                f"SUCCESS:handoff/{self.offer.unit_id} to={self.claim.session_id} "
                f"artifacts={len(self.artifact_status)} degraded=0"
            )
        return (
            f"FAILED:handoff/{self.offer.unit_id} to={self.claim.session_id} "
            f"degraded={list(self.degraded_capabilities)} "
            f"missing_artifacts={list(self.missing_artifacts)}"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "handoff_result",
            "offer": self.offer.to_dict(),
            "claim": self.claim.to_dict(),
            "negotiation": self.negotiation.to_dict(),
            "artifact_status": [a.to_dict() for a in self.artifact_status],
            "vendor_comparison": self.vendor_comparison,
            "vendor_reason": self.vendor_reason,
            "clean": self.clean,
            "degraded_capabilities": list(self.degraded_capabilities),
            "missing_artifacts": list(self.missing_artifacts),
            "sentinel_line": self.sentinel_line,
        }


def offer_handoff(
    store: Store,
    *,
    unit_id: str,
    reason: str,
    required_capabilities: Iterable[str] = (),
    extra_artifacts: Sequence[str | Path] = (),
    now: float | None = None,
) -> HandoffOffer:
    """Create an OPEN offer for ``unit_id``, carrying its preserved artifacts.

    Reads the claim for the artifact list and the fingerprint, so the receiving session inherits
    the SAME work definition rather than a re-derived one.
    """
    store.initialise()
    at = store.clock() if now is None else now
    raw = store.read(store.path_for("claims", unit_id))
    if raw is None:
        raise StoreCorrupt(f"cannot offer a handoff for {unit_id!r}: no claim record")
    claim = Claim.from_dict(raw)
    if claim.state is ClaimState.COMPLETED:
        raise StoreCorrupt(
            f"unit {unit_id!r} is COMPLETED; handing off finished work would re-open a closed unit"
        )
    artifacts = tuple(
        sorted({*claim.artifacts, *(str(Path(a)) for a in extra_artifacts)})
    )
    offer = HandoffOffer(
        offer_id=f"handoff-{uuid.uuid4().hex[:12]}",
        unit_id=unit_id,
        fingerprint=claim.fingerprint,
        from_session=claim.session_id,
        from_adapter=claim.adapter_id,
        from_vendor=claim.vendor,
        reason=reason,
        created_at=at,
        artifacts=artifacts,
        receipt_path=claim.receipt_path,
        required_capabilities=tuple(sorted(set(required_capabilities))),
    )
    store.write_atomic(store.path_for("handoffs", offer.offer_id), offer.to_dict())
    store.journal(
        "handoff.offered",
        offer_id=offer.offer_id,
        unit_id=unit_id,
        from_session=claim.session_id,
        artifacts=list(artifacts),
        reason=reason,
    )
    return offer


def open_offers(
    store: Store, *, unit_id: str | None = None
) -> tuple[HandoffOffer, ...]:
    out = [
        offer
        for _n, raw in store.iter_records("handoffs")
        if (offer := HandoffOffer.from_dict(raw)).state is OfferState.OPEN
        and (unit_id is None or offer.unit_id == unit_id)
    ]
    return tuple(sorted(out, key=lambda o: (o.created_at, o.offer_id)))


def decline_handoff(store: Store, offer_id: str, *, reason: str) -> HandoffOffer:
    """Record a refusal WITHOUT closing the offer to others.

    The state becomes DECLINED only when the offerer withdraws; a receiver's refusal is journalled
    and the offer stays OPEN, because one adapter's inability is not the unit's death.
    """
    offer = _load_offer(store, offer_id)
    store.journal(
        "handoff.declined", offer_id=offer_id, unit_id=offer.unit_id, reason=reason
    )
    return offer


def _load_offer(store: Store, offer_id: str) -> HandoffOffer:
    raw = store.read(store.path_for("handoffs", offer_id))
    if raw is None:
        raise StoreCorrupt(f"no handoff offer {offer_id!r}")
    return HandoffOffer.from_dict(raw)


#: Claim states in which the unit is not occupied and a takeover needs no vacating step.
_VACANT_STATES = frozenset(
    {ClaimState.ABANDONED, ClaimState.RELEASED, ClaimState.HANDED_OFF}
)


def _current_claim(store: Store, offer: HandoffOffer) -> Claim:
    raw = store.read(store.path_for("claims", offer.unit_id))
    if raw is None:
        raise StoreCorrupt(
            f"offer {offer.offer_id!r} names unit {offer.unit_id!r} which has no claim record"
        )
    return Claim.from_dict(raw)


def accept_handoff(
    store: Store,
    *,
    offer_id: str,
    session_id: str,
    adapter: VendorAdapter,
    unit: Mapping[str, Any],
    now: float | None = None,
) -> HandoffResult:
    """Accept an offer: re-negotiate, take the claim over, and carry the artifacts.

    ``unit`` is the work-unit mapping, required because the incoming claim must fingerprint to the
    SAME work. A mismatch is refused by :func:`~coordination.claims.acquire_claim` as
    FINGERPRINT-MISMATCH rather than accepted as a near-enough handoff.
    """
    at = store.clock() if now is None else now
    offer = _load_offer(store, offer_id)
    if offer.state is not OfferState.OPEN:
        raise StoreCorrupt(
            f"offer {offer_id!r} is {offer.state.value}, not OPEN; it cannot be accepted twice"
        )

    # ---- every refusal below happens BEFORE anything is mutated ------------------------------
    # Ordering is the contract: a refused handoff must leave the store and the artifacts exactly
    # as they were. Marking the outgoing claim first and validating second would leave a unit
    # vacated by a handoff that never happened.
    incoming_fp = claim_fingerprint(unit)
    if incoming_fp != offer.fingerprint:
        store.journal(
            "handoff.refused",
            offer_id=offer_id,
            unit_id=offer.unit_id,
            session_id=session_id,
            reason="fingerprint-mismatch",
            offered=offer.fingerprint,
            presented=incoming_fp,
        )
        raise HandoffRefused(
            f"the work definition presented for {offer.unit_id!r} does not match the offer "
            f"(offered {offer.fingerprint[:12]}, presented {incoming_fp[:12]}). A near-enough "
            "handoff is not a handoff: the receiving session would inherit artifacts produced "
            "under a different contract.",
            offer_id=offer_id,
            missing=(),
        )

    negotiation = adapter.negotiate(offer.required_capabilities)
    if negotiation.verdict is NegotiationVerdict.REFUSED:
        missing = tuple(f.capability for f in negotiation.blocking) or tuple(
            f"{a}+{b}" for a, b, _r in negotiation.conflicts
        )
        store.journal(
            "handoff.refused",
            offer_id=offer_id,
            unit_id=offer.unit_id,
            session_id=session_id,
            adapter_id=adapter.adapter_id,
            missing=list(missing),
            negotiation=negotiation.to_dict(),
        )
        raise HandoffRefused(
            f"session {session_id!r} on adapter {adapter.adapter_id!r} cannot take unit "
            f"{offer.unit_id!r}: missing {list(missing)}. The offer stays OPEN; nothing was "
            "reassigned and no artifact was touched.",
            offer_id=offer_id,
            missing=missing,
        )

    outgoing = _current_claim(store, offer)
    if outgoing.state is ClaimState.COMPLETED:
        raise HandoffRefused(
            f"unit {offer.unit_id!r} became COMPLETED after the offer was made; accepting would "
            "re-open finished work",
            offer_id=offer_id,
            missing=(),
        )
    if (
        outgoing.state not in _VACANT_STATES
        and outgoing.session_id != offer.from_session
    ):
        raise HandoffRefused(
            f"stale offer: {offer.unit_id!r} is now held by {outgoing.session_id!r}, not by the "
            f"offering session {offer.from_session!r}. The unit moved on; re-offer it.",
            offer_id=offer_id,
            missing=(),
        )
    if outgoing.state not in _VACANT_STATES:
        # The offering session still formally holds the claim - either it is handing its own work
        # over voluntarily, or it crashed and recovery has not vacated the claim yet. The OFFER is
        # the authorisation, so vacate the claim explicitly and record it as HANDED-OFF rather
        # than as ABANDONED: somebody specific is taking it.
        mark_handed_off(
            store,
            offer.unit_id,
            note=f"handed off to {session_id} via {offer_id}",
            now=at,
        )

    claim_result = acquire_claim(
        store,
        unit_id=offer.unit_id,
        unit=unit,
        session_id=session_id,
        adapter_id=adapter.adapter_id,
        vendor=adapter.vendor,
        now=at,
        takeover=True,
    )
    if not claim_result.granted or claim_result.claim is None:
        store.journal(
            "handoff.blocked",
            offer_id=offer_id,
            unit_id=offer.unit_id,
            session_id=session_id,
            outcome=claim_result.outcome.value,
            reason=claim_result.reason,
        )
        raise HandoffRefused(
            f"claim takeover for {offer.unit_id!r} was not granted: "
            f"{claim_result.outcome.value} - {claim_result.reason}",
            offer_id=offer_id,
            missing=(),
        )

    claim = claim_result.claim
    merged_artifacts = tuple(sorted({*claim.artifacts, *offer.artifacts}))
    if merged_artifacts != claim.artifacts:
        claim = replace(claim, artifacts=merged_artifacts)
        store.write_atomic(store.path_for("claims", offer.unit_id), claim.to_dict())
    status = inspect_artifacts(merged_artifacts)

    comparison, vendor_reason, _detail = vendor_identity.compare(
        offer.from_vendor, adapter.vendor
    )

    store.write_atomic(
        store.path_for("handoffs", offer_id),
        replace(
            offer, state=OfferState.ACCEPTED, accepted_by=session_id, accepted_at=at
        ).to_dict(),
    )
    result = HandoffResult(
        offer=offer,
        claim=claim,
        negotiation=negotiation,
        artifact_status=status,
        vendor_comparison=comparison.value,
        vendor_reason=vendor_reason,
    )
    store.journal(
        "handoff.accepted",
        offer_id=offer_id,
        unit_id=offer.unit_id,
        from_session=offer.from_session,
        to_session=session_id,
        adapter_id=adapter.adapter_id,
        negotiation_verdict=negotiation.verdict.value,
        degraded=list(result.degraded_capabilities),
        artifacts_present=[a.path for a in status if a.present],
        artifacts_missing=list(result.missing_artifacts),
        vendor_comparison=comparison.value,
        clean=result.clean,
    )
    return result
