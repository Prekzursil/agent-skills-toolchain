"""Vendor-specific adapter boundaries, and the mechanism that makes a refusal LOUD.

The boundary is drawn at the ADAPTER, not at the vendor. ``codex-cli`` on this Windows box
refuses ``sandbox.enforced`` while the same vendor's hosted API has no such concept; folding both
into "openai" would erase the only distinction that matters at dispatch time.

THE DEGRADE-LOUDLY MECHANISM (spec line 10983)

Three properties, each of which was chosen because its opposite is a measured failure on this
estate:

1. **A refusal raises a TYPED exception, never returns a falsy result.** ``CapabilityUnavailable``
   carries the adapter id, the capability id, and the preserved artifact paths. A boolean ``False``
   return would be indistinguishable from "no work to do".

2. **A refusal is converted to a terminal state of ``BLOCKED``, never ``FAILED`` and never
   ``SUCCESS``.** BLOCKED says "this adapter cannot do this", which is a routing fact; FAILED would
   say "the work was attempted and went wrong", which is false and would burn a retry.

3. **The work artifact survives the refusal.** ``preserve`` records the paths and asserts they are
   still on disk; nothing in this module deletes an artifact. The spec sentence is *"Degrade loudly
   AND preserve the work artifact"* - two obligations, and the second is the one an exception
   handler usually drops.

WHAT AN ADAPTER MAY NOT DO, ENFORCED BY TEST: silently substitute a different adapter. There is no
fallback chain in this module. ``route`` returns every candidate's negotiation so the CALLER picks
with the evidence in hand; it never picks a second-best adapter on its own, because a substitution
the caller did not ask for is exactly "pretending full interchangeability".
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping

from . import _libpath  # noqa: F401  - side effect: platform/lib on sys.path
from .capability import (
    CapabilityProfile,
    CapabilityRegistry,
    Negotiation,
    NegotiationVerdict,
    Support,
    default_registry,
    negotiate,
)
from .errors import CapabilityUnavailable

import vendor_identity  # noqa: E402  - resolved by _libpath above

__all__ = [
    "ADAPTER_REGISTRY_PATH",
    "AdapterRegistry",
    "AdapterStatus",
    "DegradedOutcome",
    "RoutingDecision",
    "VendorAdapter",
    "load_adapter_registry",
    "route",
]

ADAPTER_REGISTRY_PATH = Path(__file__).resolve().parent / "ADAPTER-REGISTRY.json"


class AdapterStatus(str, Enum):
    MEASURED_PARTIAL = "MEASURED-PARTIAL"
    DECLARED_UNMEASURED = "DECLARED-UNMEASURED"


@dataclass(frozen=True)
class DegradedOutcome:
    """What a refusal produces. Structurally incapable of reading as a success.

    There is no ``SUCCESS`` value for ``terminal_state`` here, and ``ok`` is a hard ``False``
    property rather than a field, so no construction path can flip it.
    """

    adapter_id: str
    unit_id: str
    capability: str
    reason: str
    preserved_artifacts: tuple[str, ...]
    terminal_state: str = "BLOCKED"

    @property
    def ok(self) -> bool:
        return False

    @property
    def sentinel_line(self) -> str:
        return (
            f"FAILED:{self.unit_id} capability-unavailable "
            f"adapter={self.adapter_id} capability={self.capability} "
            f"preserved={len(self.preserved_artifacts)}"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "degraded_outcome",
            "adapter_id": self.adapter_id,
            "unit_id": self.unit_id,
            "capability": self.capability,
            "reason": self.reason,
            "terminal_state": self.terminal_state,
            "preserved_artifacts": list(self.preserved_artifacts),
            "sentinel_line": self.sentinel_line,
        }


@dataclass(frozen=True)
class VendorAdapter:
    """One concrete agent runtime this platform can dispatch to."""

    adapter_id: str
    vendor: str
    tool: str
    status: AdapterStatus
    profile: CapabilityProfile
    notes: tuple[str, ...] = ()

    # ------------------------------------------------------------------ identity

    @property
    def vendor_canonical(self) -> str | None:
        return vendor_identity.resolve(self.vendor).canonical_id

    def establishes_distinctness(self) -> bool:
        """Whether this adapter's vendor can be one half of a cross-vendor pair."""
        return vendor_identity.resolve(self.vendor).establishes_distinctness

    def is_cross_vendor_with(
        self, other: "VendorAdapter | str"
    ) -> vendor_identity.Comparison:
        """Three-valued, delegated to the canonical resolver. Never a string comparison."""
        other_vendor = other.vendor if isinstance(other, VendorAdapter) else other
        comparison, _reason, _detail = vendor_identity.compare(
            self.vendor, other_vendor
        )
        return comparison

    # ---------------------------------------------------------------- boundaries

    def supports(
        self, capability: str, registry: CapabilityRegistry | None = None
    ) -> Support:
        return self.profile.support(capability, registry)

    def require(
        self,
        capability: str,
        *,
        unit_id: str,
        preserved_artifacts: Iterable[str | Path] = (),
        registry: CapabilityRegistry | None = None,
    ) -> None:
        """Assert the adapter can do ``capability``. Raises loudly when it cannot.

        The exception - not a return value - is the boundary. A caller that forgets to check a
        boolean would proceed; a caller that forgets to catch an exception cannot.
        """
        support = self.profile.support(capability, registry)
        if support is Support.OFFERED:
            return
        preserved = preserve(preserved_artifacts)
        cap = (registry or default_registry()).get(capability)
        if support is Support.REFUSED:
            detail = cap.degradation_note or cap.provenance
            why = f"measured UNAVAILABLE on this adapter: {detail}"
        else:
            why = (
                "never measured on this adapter; UNMEASURED is not OFFERED. Promote it in "
                "ADAPTER-REGISTRY.json only with a recorded probe."
            )
        raise CapabilityUnavailable(
            f"adapter {self.adapter_id!r} cannot provide {capability!r} for unit {unit_id!r}: {why}",
            adapter_id=self.adapter_id,
            capability=capability,
            preserved_artifacts=preserved,
        )

    def degrade(
        self,
        *,
        unit_id: str,
        capability: str,
        reason: str,
        preserved_artifacts: Iterable[str | Path] = (),
    ) -> DegradedOutcome:
        """Build the BLOCKED outcome for a refusal, preserving the artifacts."""
        return DegradedOutcome(
            adapter_id=self.adapter_id,
            unit_id=unit_id,
            capability=capability,
            reason=reason,
            preserved_artifacts=preserve(preserved_artifacts),
        )

    def negotiate(
        self, required: Iterable[str], registry: CapabilityRegistry | None = None
    ) -> Negotiation:
        return negotiate(required, self.profile, registry)

    def to_dict(self) -> dict[str, Any]:
        return {
            "adapter_id": self.adapter_id,
            "vendor": self.vendor,
            "vendor_canonical": self.vendor_canonical,
            "tool": self.tool,
            "status": self.status.value,
            "profile": self.profile.to_dict(),
        }


def preserve(paths: Iterable[str | Path]) -> tuple[str, ...]:
    """Normalise artifact paths for a preservation record.

    Deliberately does NOT delete, move, or truncate anything, and deliberately does not drop a
    path that is currently missing - a missing artifact is information the receipt must carry, not
    a reason to shorten the list.
    """
    return tuple(str(Path(p)) for p in paths)


@dataclass(frozen=True)
class AdapterRegistry:
    registry_id: str
    adapters: Mapping[str, VendorAdapter]

    def get(self, adapter_id: str) -> VendorAdapter:
        try:
            return self.adapters[adapter_id]
        except KeyError as exc:
            known = ", ".join(sorted(self.adapters))
            raise KeyError(
                f"adapter {adapter_id!r} is not in {self.registry_id}; registered: {known}"
            ) from exc

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(sorted(self.adapters))


def load_adapter_registry(path: Path | str | None = None) -> AdapterRegistry:
    raw = json.loads(Path(path or ADAPTER_REGISTRY_PATH).read_text(encoding="utf-8"))
    adapters: dict[str, VendorAdapter] = {}
    for entry in raw["adapters"]:
        adapter = VendorAdapter(
            adapter_id=entry["adapter_id"],
            vendor=entry["vendor"],
            tool=entry["tool"],
            status=AdapterStatus(entry["status"]),
            profile=CapabilityProfile(
                adapter_id=entry["adapter_id"],
                offers=frozenset(entry.get("offers", ())),
                refuses=frozenset(entry.get("refuses", ())),
            ),
            notes=tuple(entry.get("notes", ())),
        )
        adapters[adapter.adapter_id] = adapter
    return AdapterRegistry(registry_id=raw["registry_id"], adapters=adapters)


@dataclass(frozen=True)
class RoutingDecision:
    """Every candidate's negotiation. The CALLER chooses; this never substitutes."""

    unit_id: str
    required: tuple[str, ...]
    negotiations: Mapping[str, Negotiation]

    @property
    def agreed(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                a
                for a, n in self.negotiations.items()
                if n.verdict is NegotiationVerdict.AGREED
            )
        )

    @property
    def degraded(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                a
                for a, n in self.negotiations.items()
                if n.verdict is NegotiationVerdict.DEGRADED
            )
        )

    @property
    def refused(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                a
                for a, n in self.negotiations.items()
                if n.verdict is NegotiationVerdict.REFUSED
            )
        )

    @property
    def any_eligible(self) -> bool:
        return bool(self.agreed or self.degraded)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "routing_decision",
            "unit_id": self.unit_id,
            "required": list(self.required),
            "agreed": list(self.agreed),
            "degraded": list(self.degraded),
            "refused": list(self.refused),
            "negotiations": {
                a: n.to_dict() for a, n in sorted(self.negotiations.items())
            },
        }


def route(
    unit_id: str,
    required: Iterable[str],
    candidates: Iterable[VendorAdapter],
    registry: CapabilityRegistry | None = None,
) -> RoutingDecision:
    """Negotiate ``required`` against every candidate and return ALL the results.

    No preference order, no fallback, no auto-selection. The absence of a ``chosen`` field is
    deliberate: a substitution the caller did not ask for is the interchangeability lie the spec
    forbids, and a routing helper that returns one winner invites exactly that.
    """
    req = tuple(sorted(set(required)))
    return RoutingDecision(
        unit_id=unit_id,
        required=req,
        negotiations={a.adapter_id: a.negotiate(req, registry) for a in candidates},
    )
