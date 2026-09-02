"""Work claims, work fingerprints, and duplicate-work suppression.

TWO DIFFERENT DUPLICATES, BOTH SUPPRESSED

1. **Same unit id, two sessions.** Prevented atomically: the claim file is created with
   ``O_CREAT | O_EXCL``, so exactly one session wins the create even under a genuine race. A
   read-then-write check would let both sessions observe "unclaimed" and both proceed.

2. **Different unit ids, same WORK.** This is the expensive one and it is invisible to an id
   check. Suppressed by a content fingerprint over the unit's SEMANTIC CORE
   (:data:`WORK_IDENTITY_FIELDS`) - what is asked, of what inputs, producing which artifact under
   which schema, proven by which evidence and sentinel.

``assigned_model_vendor_role`` is deliberately NOT part of the fingerprint. The same work handed to
two vendors is the same work; whether that duplication is WANTED (a deliberate cross-vendor
adversarial re-run) or WASTE is a decision the caller must declare, so intentional duplication
requires ``allow_duplicate=True`` with a written reason and is recorded as such. Implicit
duplication is the failure mode; declared duplication is a legitimate strategy.

WHAT A CLAIM DOES NOT DO: it does not serialise file writes. Claims stop wasted effort; FILE
LEASES (``leases.py``) are the mutual exclusion for bytes on disk. The distinction matters for the
one residual race documented below, where the worst case is duplicated effort rather than a
corrupted file.

RESIDUAL RACE (leak L-08), STATED RATHER THAN HIDDEN: taking over an ABANDONED or RELEASED claim is a
read-then-write, so two sessions can in principle both take over the same abandoned claim. It
requires ``takeover=True`` (never implicit), both takeovers appear in the journal, and the cost is
duplicated work, not corruption - the lease layer still serialises the writes. Closing it properly
would need a compare-and-swap primitive the filesystem does not offer for an EXISTING file; the
experiment that would settle whether it matters in practice is a concurrency harness with N
sessions racing one abandoned claim, which this unit did NOT run (NOT-CHECKED).
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Sequence

from .errors import StoreCorrupt
from .session import DEFAULT_HEARTBEAT_TTL, Liveness, SessionRecord, classify
from .store import Store, fingerprint_bytes

__all__ = [
    "WORK_IDENTITY_FIELDS",
    "Claim",
    "ClaimOutcome",
    "ClaimResult",
    "ClaimState",
    "abandon_claim",
    "acquire_claim",
    "claim_view",
    "complete_claim",
    "fingerprint",
    "record_artifacts",
    "release_claim",
]

#: The semantic core of a work unit. Order is irrelevant (the digest sorts), but membership is
#: load-bearing: adding a cosmetic field here would make two identical units look different, and
#: removing a substantive one would make two different units look identical.
WORK_IDENTITY_FIELDS: tuple[str, ...] = (
    "completion_sentinel",
    "dependencies",
    "evidence_requirement",
    "inputs",
    "output_path",
    "output_schema",
    "phase",
    "question_or_target",
    "reviewer_requirement",
    "tests_required",
)


class ClaimState(str, Enum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    #: Owner died or gave up; artifacts preserved, available for handoff.
    ABANDONED = "ABANDONED"
    #: Owner released voluntarily without completing.
    RELEASED = "RELEASED"
    #: Transferred to another session via handoff.
    HANDED_OFF = "HANDED-OFF"


#: States in which a claim no longer occupies the unit.
_VACANT = frozenset({ClaimState.ABANDONED, ClaimState.RELEASED, ClaimState.HANDED_OFF})


class ClaimOutcome(str, Enum):
    GRANTED = "GRANTED"
    #: An in-force claim already covers this work. Nothing was written.
    DUPLICATE_SUPPRESSED = "DUPLICATE-SUPPRESSED"
    #: The unit is already COMPLETED. Re-running it would be waste, not progress.
    ALREADY_COMPLETE = "ALREADY-COMPLETE"
    #: Same unit id, DIFFERENT work definition. Loud: the unit was redefined under a live claim.
    FINGERPRINT_MISMATCH = "FINGERPRINT-MISMATCH"
    #: Held by a session classified DEAD. Recovery/handoff must adjudicate; never auto-stolen.
    RECOVERABLE = "RECOVERABLE"
    #: Held by a session whose liveness could not be established. Fail closed.
    BLOCKED_UNVERIFIED = "BLOCKED-UNVERIFIED"


def fingerprint(
    unit: Mapping[str, Any], fields: Sequence[str] = WORK_IDENTITY_FIELDS
) -> str:
    """Content fingerprint of a work unit's semantic core.

    The digest covers the FIELD LIST as well as the values, so a unit fingerprinted under a
    different field set cannot collide with one fingerprinted under this set. Computed over
    canonical JSON of in-memory values - never over file bytes, because git stores LF and Windows
    checks out CRLF, so a working-tree byte hash is platform-dependent.
    """
    projection = {
        "fields": list(fields),
        "values": {f: unit.get(f) for f in fields},
    }
    return hashlib.sha256(fingerprint_bytes(projection)).hexdigest()


@dataclass(frozen=True)
class Claim:
    claim_id: str
    unit_id: str
    fingerprint: str
    session_id: str
    adapter_id: str
    vendor: str
    state: ClaimState
    claimed_at: float
    updated_at: float
    artifacts: tuple[str, ...] = ()
    receipt_path: str | None = None
    takeover_seq: int = 0
    declared_duplicate_reason: str | None = None
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "claim",
            "claim_id": self.claim_id,
            "unit_id": self.unit_id,
            "fingerprint": self.fingerprint,
            "session_id": self.session_id,
            "adapter_id": self.adapter_id,
            "vendor": self.vendor,
            "state": self.state.value,
            "claimed_at": self.claimed_at,
            "updated_at": self.updated_at,
            "artifacts": list(self.artifacts),
            "receipt_path": self.receipt_path,
            "takeover_seq": self.takeover_seq,
            "declared_duplicate_reason": self.declared_duplicate_reason,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> Claim:
        try:
            return cls(
                claim_id=str(raw["claim_id"]),
                unit_id=str(raw["unit_id"]),
                fingerprint=str(raw["fingerprint"]),
                session_id=str(raw["session_id"]),
                adapter_id=str(raw.get("adapter_id", "")),
                vendor=str(raw.get("vendor", "")),
                state=ClaimState(raw["state"]),
                claimed_at=float(raw.get("claimed_at", 0.0)),
                updated_at=float(raw.get("updated_at", 0.0)),
                artifacts=tuple(str(a) for a in raw.get("artifacts", ())),
                receipt_path=(
                    None
                    if raw.get("receipt_path") is None
                    else str(raw["receipt_path"])
                ),
                takeover_seq=int(raw.get("takeover_seq", 0)),
                declared_duplicate_reason=(
                    None
                    if raw.get("declared_duplicate_reason") is None
                    else str(raw["declared_duplicate_reason"])
                ),
                note=str(raw.get("note", "")),
            )
        except (KeyError, ValueError) as exc:
            raise StoreCorrupt(f"claim record is not readable: {exc}") from exc


@dataclass(frozen=True)
class ClaimResult:
    outcome: ClaimOutcome
    claim: Claim | None
    incumbent: Claim | None = None
    incumbent_liveness: Liveness | None = None
    reason: str = ""

    @property
    def granted(self) -> bool:
        return self.outcome is ClaimOutcome.GRANTED

    @property
    def sentinel_line(self) -> str:
        if self.granted and self.claim is not None:
            return f"SUCCESS:claim/{self.claim.unit_id} claim_id={self.claim.claim_id}"
        unit = (
            (self.claim or self.incumbent).unit_id
            if (self.claim or self.incumbent)
            else "?"
        )
        return f"FAILED:claim/{unit} outcome={self.outcome.value} reason={self.reason}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "claim_result",
            "outcome": self.outcome.value,
            "reason": self.reason,
            "claim": self.claim.to_dict() if self.claim else None,
            "incumbent": self.incumbent.to_dict() if self.incumbent else None,
            "incumbent_liveness": (
                self.incumbent_liveness.value if self.incumbent_liveness else None
            ),
            "sentinel_line": self.sentinel_line,
        }


def _liveness_of(
    store: Store, session_id: str, *, now: float, heartbeat_ttl: float
) -> Liveness:
    raw = store.read(store.path_for("sessions", session_id))
    if raw is None:
        # Fail closed: a claim whose owner has no session row cannot be proven free.
        return Liveness.UNVERIFIED
    return classify(
        store, SessionRecord.from_dict(raw), now=now, heartbeat_ttl=heartbeat_ttl
    ).liveness


def _fp_primary_path(store: Store, fp: str) -> Path:
    return store.path_for("fingerprints", fp)


def _fp_dup_path(store: Store, fp: str, claim_id: str) -> Path:
    return store.path_for("fingerprints", f"{fp}.dup-{claim_id}")


def acquire_claim(
    store: Store,
    *,
    unit_id: str,
    unit: Mapping[str, Any],
    session_id: str,
    adapter_id: str = "",
    vendor: str = "",
    now: float | None = None,
    heartbeat_ttl: float = DEFAULT_HEARTBEAT_TTL,
    allow_duplicate: bool = False,
    duplicate_reason: str | None = None,
    takeover: bool = False,
) -> ClaimResult:
    """Claim ``unit_id`` for ``session_id``, or explain why not."""
    store.initialise()
    at = store.clock() if now is None else now
    fp = fingerprint(unit)
    if allow_duplicate and not (duplicate_reason and duplicate_reason.strip()):
        raise StoreCorrupt(
            "allow_duplicate=True requires a written duplicate_reason: undeclared duplication is "
            "the failure mode this suppression exists to catch"
        )

    claim = Claim(
        claim_id=f"claim-{uuid.uuid4().hex[:12]}",
        unit_id=unit_id,
        fingerprint=fp,
        session_id=session_id,
        adapter_id=adapter_id,
        vendor=vendor,
        state=ClaimState.ACTIVE,
        claimed_at=at,
        updated_at=at,
        declared_duplicate_reason=duplicate_reason if allow_duplicate else None,
    )
    claim_path = store.path_for("claims", unit_id)

    if not store.create_exclusive(claim_path, claim.to_dict()):
        raw = store.read(claim_path)
        if raw is None:  # pragma: no cover - the file existed a moment ago
            raise StoreCorrupt(
                f"claim for {unit_id!r} vanished between create and read"
            )
        incumbent = Claim.from_dict(raw)
        result = _classify_incumbent(
            store,
            incumbent=incumbent,
            newcomer=claim,
            at=at,
            heartbeat_ttl=heartbeat_ttl,
            takeover=takeover,
        )
        if result is not None:
            store.journal(
                "claim.denied",
                unit_id=unit_id,
                session_id=session_id,
                outcome=result.outcome.value,
                reason=result.reason,
            )
            return result
        # Takeover of a vacant claim. Read-then-write; see the module docstring's residual race.
        claim = replace(
            claim,
            takeover_seq=incumbent.takeover_seq + 1,
            artifacts=incumbent.artifacts,
        )
        store.write_atomic(claim_path, claim.to_dict())

    dup = _register_fingerprint(
        store,
        claim=claim,
        at=at,
        heartbeat_ttl=heartbeat_ttl,
        allow_duplicate=allow_duplicate,
    )
    if dup is not None:
        # Roll back the claim we just created: nobody else can hold it, so removal is safe.
        store.delete(claim_path)
        store.journal(
            "claim.denied",
            unit_id=unit_id,
            session_id=session_id,
            outcome=dup.outcome.value,
            reason=dup.reason,
        )
        return dup

    store.journal(
        "claim.granted",
        unit_id=unit_id,
        claim_id=claim.claim_id,
        session_id=session_id,
        fingerprint=fp,
        takeover_seq=claim.takeover_seq,
        declared_duplicate_reason=claim.declared_duplicate_reason,
    )
    return ClaimResult(ClaimOutcome.GRANTED, claim, reason="claim created")


def _classify_incumbent(
    store: Store,
    *,
    incumbent: Claim,
    newcomer: Claim,
    at: float,
    heartbeat_ttl: float,
    takeover: bool,
) -> ClaimResult | None:
    """Return the denial, or ``None`` when the newcomer may take the claim over."""
    if incumbent.state is ClaimState.COMPLETED:
        return ClaimResult(
            ClaimOutcome.ALREADY_COMPLETE,
            None,
            incumbent,
            None,
            reason=(
                f"unit {incumbent.unit_id!r} is already COMPLETED by {incumbent.session_id!r}; "
                "re-running it is waste. Verify with the shared reducer, do not re-execute."
            ),
        )
    if incumbent.fingerprint != newcomer.fingerprint:
        # Checked BEFORE the vacant/takeover branch and deliberately not waivable by
        # ``takeover``. Inheriting an abandoned claim's artifacts under a DIFFERENT work
        # definition would attach one unit's work product to another unit's contract, which is
        # the data-corrupting direction of the error. A genuine redefinition must retire the old
        # unit id rather than reuse it.
        return ClaimResult(
            ClaimOutcome.FINGERPRINT_MISMATCH,
            None,
            incumbent,
            None,
            reason=(
                f"unit id {incumbent.unit_id!r} is claimed with a DIFFERENT work definition "
                f"(held {incumbent.fingerprint[:12]}, requested {newcomer.fingerprint[:12]}), "
                f"incumbent state={incumbent.state.value}. Resolve the definition before "
                "claiming; a takeover does not waive this."
            ),
        )
    if incumbent.state in _VACANT:
        if takeover:
            return None
        return ClaimResult(
            ClaimOutcome.RECOVERABLE,
            None,
            incumbent,
            None,
            reason=(
                f"claim is {incumbent.state.value}; artifacts are preserved. Pass takeover=True "
                "or accept a handoff - a vacant claim is never taken implicitly."
            ),
        )
    liveness = _liveness_of(
        store, incumbent.session_id, now=at, heartbeat_ttl=heartbeat_ttl
    )
    if liveness is Liveness.LIVE:
        return ClaimResult(
            ClaimOutcome.DUPLICATE_SUPPRESSED,
            None,
            incumbent,
            liveness,
            reason=(
                f"session {incumbent.session_id!r} holds an ACTIVE claim and is LIVE by both "
                "signals; duplicating the unit would burn a second budget for one result"
            ),
        )
    if liveness is Liveness.DEAD:
        return ClaimResult(
            ClaimOutcome.RECOVERABLE,
            None,
            incumbent,
            liveness,
            reason=(
                f"holder {incumbent.session_id!r} is DEAD by both signals; run recovery to abandon "
                "the claim and preserve its artifacts, then accept the handoff"
            ),
        )
    if liveness is Liveness.CLOSED:
        return ClaimResult(
            ClaimOutcome.RECOVERABLE,
            None,
            incumbent,
            liveness,
            reason=(
                f"holder {incumbent.session_id!r} closed gracefully while still holding an ACTIVE "
                "claim; recovery must adjudicate whether the work finished"
            ),
        )
    return ClaimResult(
        ClaimOutcome.BLOCKED_UNVERIFIED,
        None,
        incumbent,
        liveness,
        reason=(
            f"holder {incumbent.session_id!r} liveness is UNVERIFIED; one signal is not evidence, "
            "so the claim is not reassigned. Force it only with an explicit recovery decision."
        ),
    )


def _register_fingerprint(
    store: Store,
    *,
    claim: Claim,
    at: float,
    heartbeat_ttl: float,
    allow_duplicate: bool,
) -> ClaimResult | None:
    """Index the fingerprint. Returns a denial when the SAME WORK is claimed under another id."""
    entry = {
        "kind": "fingerprint_index",
        "fingerprint": claim.fingerprint,
        "unit_id": claim.unit_id,
        "claim_id": claim.claim_id,
        "session_id": claim.session_id,
        "at": at,
    }
    primary = _fp_primary_path(store, claim.fingerprint)
    if store.create_exclusive(primary, entry):
        return None
    existing = store.read(primary)
    if existing is None:  # pragma: no cover - existed a moment ago
        raise StoreCorrupt(f"fingerprint index for {claim.fingerprint} vanished")
    if str(existing.get("unit_id")) == claim.unit_id:
        # Same unit re-claimed after a takeover. Point the index at the new claim.
        store.write_atomic(primary, entry)
        return None
    other_unit = str(existing.get("unit_id"))
    other_raw = store.read(store.path_for("claims", other_unit))
    other = Claim.from_dict(other_raw) if other_raw else None
    other_liveness = (
        _liveness_of(store, other.session_id, now=at, heartbeat_ttl=heartbeat_ttl)
        if other
        else None
    )
    occupied = other is not None and (
        other.state is ClaimState.COMPLETED
        or (
            other.state not in _VACANT
            and other_liveness in {Liveness.LIVE, Liveness.UNVERIFIED}
        )
    )
    if occupied and not allow_duplicate:
        return ClaimResult(
            ClaimOutcome.DUPLICATE_SUPPRESSED,
            None,
            other,
            other_liveness,
            reason=(
                f"unit {claim.unit_id!r} has the same work fingerprint "
                f"{claim.fingerprint[:12]} as unit {other_unit!r} "
                f"(state={other.state.value if other else '?'}"
                + (f", holder={other_liveness.value}" if other_liveness else "")
                + "). Two ids, one piece of work. Pass allow_duplicate=True with a written reason "
                "if the duplication is deliberate."
            ),
        )
    # Either the other claim is vacant/dead, or the duplication is declared. Record a side entry
    # so the index stays append-only and every duplicate is auditable.
    store.write_atomic(
        _fp_dup_path(store, claim.fingerprint, claim.claim_id),
        {**entry, "declared_duplicate_reason": claim.declared_duplicate_reason},
    )
    return None


def claim_view(
    store: Store,
    unit_id: str,
    *,
    now: float | None = None,
    heartbeat_ttl: float = DEFAULT_HEARTBEAT_TTL,
) -> tuple[Claim, Liveness] | None:
    raw = store.read(store.path_for("claims", unit_id))
    if raw is None:
        return None
    claim = Claim.from_dict(raw)
    at = store.clock() if now is None else now
    return claim, _liveness_of(
        store, claim.session_id, now=at, heartbeat_ttl=heartbeat_ttl
    )


def _transition(
    store: Store,
    unit_id: str,
    state: ClaimState,
    *,
    artifacts: Sequence[str | Path] = (),
    receipt_path: str | Path | None = None,
    note: str = "",
    now: float | None = None,
) -> Claim:
    path = store.path_for("claims", unit_id)
    raw = store.read(path)
    if raw is None:
        raise StoreCorrupt(f"no claim for unit {unit_id!r}")
    claim = Claim.from_dict(raw)
    merged = tuple(sorted({*claim.artifacts, *(str(Path(a)) for a in artifacts)}))
    updated = replace(
        claim,
        state=state,
        updated_at=store.clock() if now is None else now,
        artifacts=merged,
        receipt_path=(
            str(receipt_path) if receipt_path is not None else claim.receipt_path
        ),
        note=note or claim.note,
    )
    store.write_atomic(path, updated.to_dict())
    store.journal(
        "claim.transition",
        unit_id=unit_id,
        claim_id=claim.claim_id,
        state=state.value,
        artifacts=list(merged),
        receipt_path=updated.receipt_path,
    )
    return updated


def mark_handed_off(
    store: Store, unit_id: str, *, note: str = "", now: float | None = None
) -> Claim:
    """Move a claim to HANDED-OFF, vacating the unit for the receiving session.

    Separate from ABANDONED because the two are different histories: abandoned means nobody has
    it, handed-off means somebody specific took it. Recovery produces the first; an accepted
    handoff produces the second.
    """
    return _transition(store, unit_id, ClaimState.HANDED_OFF, note=note, now=now)


def record_artifacts(
    store: Store,
    unit_id: str,
    artifacts: Sequence[str | Path],
    *,
    now: float | None = None,
) -> Claim:
    """Attach artifact paths to a claim WITHOUT changing its state.

    A running unit must be able to register the partial work it has produced, because that list is
    what crash recovery preserves and what a handoff carries. Recording it only at completion
    would mean a crashed unit's artifacts are invisible - exactly the work the spec says to keep.
    """
    path = store.path_for("claims", unit_id)
    raw = store.read(path)
    if raw is None:
        raise StoreCorrupt(f"no claim for unit {unit_id!r}")
    return _transition(
        store, unit_id, Claim.from_dict(raw).state, artifacts=artifacts, now=now
    )


def complete_claim(
    store: Store,
    unit_id: str,
    *,
    receipt_path: str | Path,
    artifacts: Sequence[str | Path] = (),
    now: float | None = None,
) -> Claim:
    """Mark COMPLETED. Records the receipt path; the VERDICT belongs to the shared reducer.

    Leak L-10: ``COMPLETED`` here means a session ASSERTS it finished. Whether the unit IS complete
    is decided only by ``platform/lib/completion_predicate.py`` (twelve conditions), reached through
    ``reducer.reduce_claim``. Two vocabularies use the same English word for different things, which
    is how a self-certifying receipt gets believed. Nothing in this module evaluates completion - a
    second opinion computed here would be a duplicate control plane.
    """
    return _transition(
        store,
        unit_id,
        ClaimState.COMPLETED,
        artifacts=artifacts,
        receipt_path=receipt_path,
        now=now,
    )


def release_claim(
    store: Store,
    unit_id: str,
    *,
    artifacts: Sequence[str | Path] = (),
    note: str = "",
    now: float | None = None,
) -> Claim:
    return _transition(
        store, unit_id, ClaimState.RELEASED, artifacts=artifacts, note=note, now=now
    )


def abandon_claim(
    store: Store,
    unit_id: str,
    *,
    artifacts: Sequence[str | Path] = (),
    note: str = "",
    now: float | None = None,
) -> Claim:
    """Mark ABANDONED, preserving artifacts. Never deletes a file (spec line 10983)."""
    return _transition(
        store, unit_id, ClaimState.ABANDONED, artifacts=artifacts, note=note, now=now
    )
