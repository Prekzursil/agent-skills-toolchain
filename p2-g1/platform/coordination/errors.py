"""Typed coordination failures.

Every error here exists so a failure is LOUD and CLASSIFIED rather than absorbed. The estate's
worst measured defect class is a guard that converts a bug into a green (a defensive
``hasattr`` swallowing an ``AttributeError`` and yielding "0/0 conditions, 0 blocking", which an
aggregate read as PASS). Nothing in this package catches a bare ``Exception``; each failure mode
has a name, and the name is what reaches the receipt.
"""

from __future__ import annotations

__all__ = [
    "CapabilityUnavailable",
    "CoordinationError",
    "DuplicateControlPlane",
    "HandoffRefused",
    "LeaseConflict",
    "PathOutsideRoot",
    "StoreCorrupt",
    "UnknownCapability",
]


class CoordinationError(Exception):
    """Base class. Never raised directly; every raise site uses a subclass."""


class StoreCorrupt(CoordinationError):
    """A record on disk is unreadable or fails its own shape check.

    Raised rather than defaulted: a coordination store that silently reads a corrupt claim as
    "no claim" would hand the same work unit to two sessions.
    """


class PathOutsideRoot(CoordinationError):
    """A lease was requested for a path that does not resolve under the declared root."""


class LeaseConflict(CoordinationError):
    """An exclusive lease was requested over a path another live session already holds."""


class UnknownCapability(CoordinationError):
    """A capability id absent from CAPABILITY-REGISTRY.json.

    Fails closed. An unrecognized capability is NOT-COMPUTABLE, and NOT-COMPUTABLE never folds
    into "supported" - that inversion is exactly how DEFECT D1 turned an unrecognized vendor
    string into a passing cross-vendor gate.
    """


class CapabilityUnavailable(CoordinationError):
    """An adapter was asked to perform an operation its vendor cannot perform.

    This is the spec's "degrade loudly" path (line 10983). It carries the preserved artifact
    paths so the work product survives the refusal.
    """

    def __init__(
        self,
        message: str,
        *,
        adapter_id: str,
        capability: str,
        preserved_artifacts: tuple[str, ...] = (),
    ) -> None:
        super().__init__(message)
        self.adapter_id = adapter_id
        self.capability = capability
        self.preserved_artifacts = preserved_artifacts


class HandoffRefused(CoordinationError):
    """A handoff was refused because the receiving session cannot satisfy the unit's contract."""

    def __init__(
        self, message: str, *, offer_id: str, missing: tuple[str, ...]
    ) -> None:
        super().__init__(message)
        self.offer_id = offer_id
        self.missing = missing


class DuplicateControlPlane(CoordinationError):
    """A second completion reducer was found inside this package.

    Duplicate control planes are forbidden: the shared reducer is
    ``platform/lib/completion_predicate.py`` and this package delegates to it.
    """
