"""Crash recovery: adjudicate what a dead session left behind, without destroying any of it.

RECOVERY IS A TWO-PHASE OPERATION AND THE PHASES ARE SEPARATE FUNCTIONS

:func:`plan_recovery` is READ-ONLY. It classifies every session, enumerates the claims and leases
each one still holds, stats their artifacts, and produces an explicit action list. Nothing on disk
changes. :func:`execute_recovery` applies a plan. The split exists so a plan can be printed,
reviewed, or diffed before anything is touched - the estate has a measured case where a
position-blind containment check was used as a delete authorisation and cost data.

THREE RULES

1. **Never reap an UNVERIFIED session's work without an explicit force.** Actions derived from an
   UNVERIFIED session carry ``requires_force=True`` and are SKIPPED by default. Reaping a live
   session's claim is the expensive direction of the error, so the default is inaction and the
   plan says loudly what it declined to do.

2. **Never delete an artifact.** Recovery marks claims ABANDONED, releases leases, and opens
   handoff offers. It stats artifacts and records PRESENT/MISSING. There is no unlink of an
   artifact anywhere in this module, and ``test_recovery.py`` asserts the bytes survive.

3. **Idempotent.** Running recovery twice must produce the same store. The second run finds no
   ACTIVE claims and no active leases for the dead sessions, so it plans zero actions.
   ``test_recovery.py`` asserts the second plan is empty AND that the store bytes are unchanged.

WHAT RECOVERY DELIBERATELY DOES NOT CLAIM

It never reports a session as "hung" or "stuck". A stale heartbeat with a held OS lock means the
process is running and not heartbeating; proving it is stuck needs orchestrator state (which units
are EXPECTED to be running) that a store scan does not contain. That case is UNVERIFIED, and the
reason string says exactly this.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Iterable

from .claims import Claim, ClaimState, abandon_claim
from .handoff import ArtifactStatus, HandoffOffer, inspect_artifacts, offer_handoff
from .leases import Lease, release_leases
from .session import DEFAULT_HEARTBEAT_TTL, Liveness, SessionView, discover
from .store import Store

__all__ = [
    "Action",
    "ActionKind",
    "RecoveryOutcome",
    "RecoveryPlan",
    "execute_recovery",
    "plan_recovery",
]


class ActionKind(str, Enum):
    #: Mark the claim ABANDONED (artifacts preserved) and open a handoff offer.
    ABANDON_AND_OFFER = "ABANDON-AND-OFFER"
    #: Release the dead session's file leases so other sessions can proceed.
    RELEASE_LEASES = "RELEASE-LEASES"
    #: A COMPLETED claim held by a dead session: nothing to recover, recorded for the audit trail.
    NOOP_COMPLETED = "NOOP-COMPLETED"


@dataclass(frozen=True)
class Action:
    kind: ActionKind
    session_id: str
    liveness: Liveness
    unit_id: str | None
    lease_ids: tuple[str, ...]
    artifacts: tuple[ArtifactStatus, ...]
    requires_force: bool
    reason: str
    required_capabilities: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "session_id": self.session_id,
            "liveness": self.liveness.value,
            "unit_id": self.unit_id,
            "lease_ids": list(self.lease_ids),
            "artifacts": [a.to_dict() for a in self.artifacts],
            "requires_force": self.requires_force,
            "reason": self.reason,
            "required_capabilities": list(self.required_capabilities),
        }


@dataclass(frozen=True)
class RecoveryPlan:
    """Read-only. Nothing has changed on disk when you hold one of these."""

    at: float
    sessions: tuple[SessionView, ...]
    actions: tuple[Action, ...]

    @property
    def dead(self) -> tuple[str, ...]:
        return tuple(v.session_id for v in self.sessions if v.liveness is Liveness.DEAD)

    @property
    def unverified(self) -> tuple[str, ...]:
        return tuple(
            v.session_id for v in self.sessions if v.liveness is Liveness.UNVERIFIED
        )

    @property
    def forced_actions(self) -> tuple[Action, ...]:
        return tuple(a for a in self.actions if a.requires_force)

    @property
    def automatic_actions(self) -> tuple[Action, ...]:
        return tuple(a for a in self.actions if not a.requires_force)

    @property
    def is_empty(self) -> bool:
        return not self.actions

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "recovery_plan",
            "at": self.at,
            "sessions": [v.to_dict() for v in self.sessions],
            "dead": list(self.dead),
            "unverified": list(self.unverified),
            "actions": [a.to_dict() for a in self.actions],
            "automatic": len(self.automatic_actions),
            "requires_force": len(self.forced_actions),
        }


@dataclass(frozen=True)
class RecoveryOutcome:
    plan: RecoveryPlan
    applied: tuple[Action, ...]
    skipped: tuple[Action, ...]
    offers: tuple[HandoffOffer, ...]
    released_leases: tuple[str, ...]
    abandoned_claims: tuple[str, ...]
    artifacts_missing: tuple[str, ...]

    @property
    def sentinel_line(self) -> str:
        if self.artifacts_missing:
            return (
                f"FAILED:recovery applied={len(self.applied)} "
                f"artifacts_missing={list(self.artifacts_missing)}"
            )
        return (
            f"SUCCESS:recovery applied={len(self.applied)}/{len(self.plan.actions)} "
            f"skipped_requires_force={len(self.skipped)} offers={len(self.offers)} "
            f"leases_released={len(self.released_leases)} artifacts_preserved=all"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "recovery_outcome",
            "plan": self.plan.to_dict(),
            "applied": [a.to_dict() for a in self.applied],
            "skipped": [a.to_dict() for a in self.skipped],
            "offers": [o.to_dict() for o in self.offers],
            "released_leases": list(self.released_leases),
            "abandoned_claims": list(self.abandoned_claims),
            "artifacts_missing": list(self.artifacts_missing),
            "sentinel_line": self.sentinel_line,
        }


#: Liveness states whose held resources are candidates for recovery, with whether force is needed.
#: CLOSED is included with requires_force=False: a graceful exit is definitive, and a session that
#: closed while still holding an ACTIVE claim left work behind that nobody is doing.
_RECOVERABLE: dict[Liveness, bool] = {
    Liveness.DEAD: False,
    Liveness.CLOSED: False,
    Liveness.UNVERIFIED: True,
}


def _claims_of(store: Store, session_id: str) -> list[Claim]:
    return [
        claim
        for _n, raw in store.iter_records("claims")
        if (claim := Claim.from_dict(raw)).session_id == session_id
    ]


def _leases_of(store: Store, session_id: str, *, at: float) -> list[Lease]:
    return [
        lease
        for _n, raw in store.iter_records("leases")
        if (lease := Lease.from_dict(raw)).session_id == session_id
        and lease.active
        and not lease.expired(at)
    ]


def plan_recovery(
    store: Store,
    *,
    now: float | None = None,
    heartbeat_ttl: float = DEFAULT_HEARTBEAT_TTL,
    required_capabilities: Iterable[str] = (),
) -> RecoveryPlan:
    """Classify every session and enumerate what needs recovering. Changes nothing."""
    at = store.clock() if now is None else now
    sessions = discover(store, now=at, heartbeat_ttl=heartbeat_ttl)
    req = tuple(sorted(set(required_capabilities)))
    actions: list[Action] = []

    for view in sessions:
        force = _RECOVERABLE.get(view.liveness)
        if force is None:
            continue  # LIVE: leave everything alone.
        for claim in _claims_of(store, view.session_id):
            if claim.state is ClaimState.COMPLETED:
                actions.append(
                    Action(
                        kind=ActionKind.NOOP_COMPLETED,
                        session_id=view.session_id,
                        liveness=view.liveness,
                        unit_id=claim.unit_id,
                        lease_ids=(),
                        artifacts=inspect_artifacts(claim.artifacts),
                        requires_force=False,
                        reason=(
                            f"unit {claim.unit_id!r} is COMPLETED; the holder being "
                            f"{view.liveness.value} does not un-finish it. Verify the receipt with "
                            "the shared reducer rather than re-running the unit."
                        ),
                    )
                )
                continue
            if claim.state is not ClaimState.ACTIVE:
                continue
            actions.append(
                Action(
                    kind=ActionKind.ABANDON_AND_OFFER,
                    session_id=view.session_id,
                    liveness=view.liveness,
                    unit_id=claim.unit_id,
                    lease_ids=(),
                    artifacts=inspect_artifacts(claim.artifacts),
                    requires_force=force,
                    reason=(
                        f"unit {claim.unit_id!r} is ACTIVE under {view.session_id!r} which is "
                        f"{view.liveness.value} ({view.reason}). Abandon the claim, preserve its "
                        f"{len(claim.artifacts)} artifact(s), and open a handoff."
                    ),
                    required_capabilities=req,
                )
            )
        leases = _leases_of(store, view.session_id, at=at)
        if leases:
            actions.append(
                Action(
                    kind=ActionKind.RELEASE_LEASES,
                    session_id=view.session_id,
                    liveness=view.liveness,
                    unit_id=None,
                    lease_ids=tuple(sorted(lease.lease_id for lease in leases)),
                    artifacts=(),
                    requires_force=force,
                    reason=(
                        f"{len(leases)} in-force lease(s) held by {view.session_id!r} which is "
                        f"{view.liveness.value}; other sessions are blocked until they are released"
                    ),
                )
            )
    return RecoveryPlan(at=at, sessions=sessions, actions=tuple(actions))


def execute_recovery(
    store: Store, plan: RecoveryPlan, *, force: bool = False, now: float | None = None
) -> RecoveryOutcome:
    """Apply ``plan``. Skips ``requires_force`` actions unless ``force=True``.

    Idempotent: applying a freshly-computed plan twice performs the second pass over an empty
    action list, because the first pass moved the claims out of ACTIVE and the leases out of
    active.
    """
    at = store.clock() if now is None else now
    applied: list[Action] = []
    skipped: list[Action] = []
    offers: list[HandoffOffer] = []
    released: list[str] = []
    abandoned: list[str] = []
    missing: list[str] = []

    for action in plan.actions:
        if action.requires_force and not force:
            skipped.append(action)
            store.journal(
                "recovery.skipped",
                kind=action.kind.value,
                session_id=action.session_id,
                unit_id=action.unit_id,
                liveness=action.liveness.value,
                reason="requires_force and force=False - refusing to reap an unverified session",
            )
            continue
        if action.kind is ActionKind.NOOP_COMPLETED:
            applied.append(action)
            store.journal(
                "recovery.noop_completed",
                session_id=action.session_id,
                unit_id=action.unit_id,
            )
            continue
        if action.kind is ActionKind.RELEASE_LEASES:
            ids = release_leases(store, lease_ids=action.lease_ids, now=at)
            released.extend(ids)
            applied.append(action)
            continue
        # ABANDON_AND_OFFER
        assert action.unit_id is not None  # guaranteed by plan_recovery
        claim = abandon_claim(
            store,
            action.unit_id,
            note=f"recovered from {action.liveness.value} session {action.session_id}",
            now=at,
        )
        abandoned.append(claim.unit_id)
        status = inspect_artifacts(claim.artifacts)
        missing.extend(a.path for a in status if not a.present)
        offer = offer_handoff(
            store,
            unit_id=claim.unit_id,
            reason=(
                f"crash recovery: holder {action.session_id} classified "
                f"{action.liveness.value}"
            ),
            required_capabilities=action.required_capabilities,
            now=at,
        )
        offers.append(offer)
        applied.append(action)

    outcome = RecoveryOutcome(
        plan=plan,
        applied=tuple(applied),
        skipped=tuple(skipped),
        offers=tuple(offers),
        released_leases=tuple(sorted(released)),
        abandoned_claims=tuple(sorted(abandoned)),
        artifacts_missing=tuple(sorted(set(missing))),
    )
    store.journal(
        "recovery.executed",
        applied=len(applied),
        skipped=len(skipped),
        force=force,
        abandoned_claims=list(outcome.abandoned_claims),
        released_leases=list(outcome.released_leases),
        artifacts_missing=list(outcome.artifacts_missing),
    )
    return outcome


def artifact_digest_report(paths: Iterable[str | Path]) -> dict[str, Any]:
    """Convenience: sizes only, never content digests of tracked source files.

    Deliberately does not hash file bytes. Git stores LF and Windows checks out CRLF, so a
    working-tree byte hash is platform-dependent - two shipped gates on this estate had exactly
    that bug and one rendered a phantom violation into a committed file. Sizes are enough to prove
    "still there and non-empty", which is what preservation means here.
    """
    status = inspect_artifacts(paths)
    return {
        "checked": len(status),
        "present": sum(1 for a in status if a.present),
        "missing": [a.path for a in status if not a.present],
        "sizes": {a.path: a.size_bytes for a in status},
        "note": "sizes only - no working-tree byte hashing (LF/CRLF platform skew)",
    }
