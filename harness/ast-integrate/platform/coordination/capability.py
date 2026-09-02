"""Capability negotiation - three-valued, fail-closed.

The whole point of this module is one sentence from the spec (line 10983): *"Do not pretend full
interchangeability where tools, context, or permissions differ."*

The mechanism is a THREE-state support model rather than a boolean:

  OFFERED     the adapter's registry entry lists the capability under ``offers``  (measured true)
  REFUSED     the adapter's registry entry lists it under ``refuses``             (measured false)
  UNMEASURED  it appears in neither list                                          (no measurement)

``UNMEASURED`` is not ``OFFERED``. That single asymmetry is what stops an unmeasured adapter from
inheriting another vendor's capability list, and it is the same asymmetry that closed DEFECT D1 -
there, "not byte-equal" was read as "a different vendor", so an unregistered string satisfied the
platform's strongest gate. Here, "not listed" is read as "not available".

A capability id absent from CAPABILITY-REGISTRY.json raises :class:`UnknownCapability`. Typos must
not negotiate: silently ignoring an unrecognized requirement is how a required capability becomes
optional.

Negotiation verdicts, and why there are three of them:

  AGREED    every required capability is OFFERED
  DEGRADED  every REQUIRED-criticality capability is OFFERED, but at least one DEGRADABLE one is
            not. The run may proceed AND the degradation is carried on the receipt. A DEGRADED
            negotiation is never reported as AGREED - "degrade loudly" means the record says so.
  REFUSED   a REQUIRED-criticality capability is REFUSED or UNMEASURED. The dispatch never starts.

There is a fourth thing that could have been done and deliberately was not: infer a capability
from a vendor name. Capabilities belong to the ADAPTER (the runtime + flags + platform), not to
the vendor - ``codex-cli`` refuses ``sandbox.enforced`` on Windows while the same vendor's hosted
API has no such notion at all.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .errors import UnknownCapability

__all__ = [
    "CAPABILITY_REGISTRY_PATH",
    "Capability",
    "CapabilityRegistry",
    "CapabilityProfile",
    "Criticality",
    "Negotiation",
    "NegotiationVerdict",
    "Support",
    "SupportFinding",
    "load_capability_registry",
    "negotiate",
]

CAPABILITY_REGISTRY_PATH = Path(__file__).resolve().parent / "CAPABILITY-REGISTRY.json"


class Criticality(str, Enum):
    REQUIRED = "REQUIRED"
    DEGRADABLE = "DEGRADABLE"


class Support(str, Enum):
    OFFERED = "OFFERED"
    REFUSED = "REFUSED"
    UNMEASURED = "UNMEASURED"


class NegotiationVerdict(str, Enum):
    AGREED = "AGREED"
    DEGRADED = "DEGRADED"
    REFUSED = "REFUSED"


@dataclass(frozen=True)
class Capability:
    """One registry entry."""

    id: str
    title: str
    criticality: Criticality
    provenance: str
    degradation_note: str | None = None
    verified_by_this_unit: bool = False

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "id": self.id,
            "title": self.title,
            "criticality": self.criticality.value,
            "provenance": self.provenance,
            "verified_by_this_unit": self.verified_by_this_unit,
        }
        if self.degradation_note:
            out["degradation_note"] = self.degradation_note
        return out


@dataclass(frozen=True)
class CapabilityRegistry:
    registry_id: str
    schema_version: str
    capabilities: Mapping[str, Capability]

    def get(self, capability_id: str) -> Capability:
        try:
            return self.capabilities[capability_id]
        except KeyError as exc:
            known = ", ".join(sorted(self.capabilities))
            raise UnknownCapability(
                f"capability {capability_id!r} is not in {self.registry_id}; "
                f"registered ids: {known}"
            ) from exc

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(sorted(self.capabilities))

    def criticality(self, capability_id: str) -> Criticality:
        return self.get(capability_id).criticality


def load_capability_registry(path: Path | str | None = None) -> CapabilityRegistry:
    raw = json.loads(Path(path or CAPABILITY_REGISTRY_PATH).read_text(encoding="utf-8"))
    caps: dict[str, Capability] = {}
    for entry in raw["capabilities"]:
        cap = Capability(
            id=entry["id"],
            title=entry["title"],
            criticality=Criticality(entry["criticality"]),
            provenance=entry["provenance"],
            degradation_note=entry.get("degradation_note"),
            verified_by_this_unit=bool(entry.get("verified_by_this_unit", False)),
        )
        if cap.id in caps:
            raise UnknownCapability(f"duplicate capability id {cap.id!r} in registry")
        caps[cap.id] = cap
    return CapabilityRegistry(
        registry_id=raw["registry_id"],
        schema_version=raw["schema_version"],
        capabilities=caps,
    )


_CACHE: CapabilityRegistry | None = None


def default_registry() -> CapabilityRegistry:
    global _CACHE
    if _CACHE is None:
        _CACHE = load_capability_registry()
    return _CACHE


@dataclass(frozen=True)
class CapabilityProfile:
    """What one adapter can and cannot do. Anything unlisted is UNMEASURED, never OFFERED."""

    adapter_id: str
    offers: frozenset[str] = frozenset()
    refuses: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        overlap = self.offers & self.refuses
        if overlap:
            raise UnknownCapability(
                f"adapter {self.adapter_id!r} both offers and refuses {sorted(overlap)}; "
                "a capability cannot be measured true and false at once"
            )

    def support(
        self, capability_id: str, registry: CapabilityRegistry | None = None
    ) -> Support:
        (registry or default_registry()).get(capability_id)  # raises on unknown id
        if capability_id in self.offers:
            return Support.OFFERED
        if capability_id in self.refuses:
            return Support.REFUSED
        return Support.UNMEASURED

    def to_dict(self) -> dict[str, Any]:
        return {
            "adapter_id": self.adapter_id,
            "offers": sorted(self.offers),
            "refuses": sorted(self.refuses),
        }


@dataclass(frozen=True)
class SupportFinding:
    """Per-capability negotiation outcome, with the reason a receipt should quote."""

    capability: str
    criticality: Criticality
    support: Support
    reason: str

    @property
    def blocks(self) -> bool:
        return (
            self.criticality is Criticality.REQUIRED
            and self.support is not Support.OFFERED
        )

    @property
    def degrades(self) -> bool:
        return (
            self.criticality is Criticality.DEGRADABLE
            and self.support is not Support.OFFERED
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability": self.capability,
            "criticality": self.criticality.value,
            "support": self.support.value,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class Negotiation:
    """The result. Read ``verdict``; ``findings`` says why, per capability."""

    adapter_id: str
    verdict: NegotiationVerdict
    findings: tuple[SupportFinding, ...]
    conflicts: tuple[tuple[str, str, str], ...] = ()
    registry_id: str = ""
    #: Capabilities positively confirmed OFFERED. Asserting the POSITIVE, never merely
    #: "nothing blocking" - a "0 blocking" aggregate read as PASS is a measured defect class.
    satisfied: tuple[str, ...] = field(default=())

    @property
    def blocking(self) -> tuple[SupportFinding, ...]:
        return tuple(f for f in self.findings if f.blocks)

    @property
    def degraded(self) -> tuple[SupportFinding, ...]:
        return tuple(f for f in self.findings if f.degrades)

    @property
    def is_agreed(self) -> bool:
        return self.verdict is NegotiationVerdict.AGREED

    @property
    def may_proceed(self) -> bool:
        """True for AGREED and DEGRADED. False for REFUSED."""
        return self.verdict is not NegotiationVerdict.REFUSED

    @property
    def sentinel_line(self) -> str:
        if self.verdict is NegotiationVerdict.AGREED:
            return (
                f"SUCCESS:negotiate/{self.adapter_id} verdict=AGREED "
                f"satisfied={len(self.satisfied)}/{len(self.findings)}"
            )
        missing = [f.capability for f in self.blocking] or [
            f.capability for f in self.degraded
        ]
        return (
            f"FAILED:negotiate/{self.adapter_id} verdict={self.verdict.value} "
            f"missing={missing}"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "capability_negotiation",
            "adapter_id": self.adapter_id,
            "registry_id": self.registry_id,
            "verdict": self.verdict.value,
            "satisfied": list(self.satisfied),
            "blocking": [f.to_dict() for f in self.blocking],
            "degraded": [f.to_dict() for f in self.degraded],
            "conflicts": [
                {"a": a, "b": b, "reason": reason} for a, b, reason in self.conflicts
            ],
            "findings": [f.to_dict() for f in self.findings],
            "sentinel_line": self.sentinel_line,
        }


#: Capability pairs that cannot both be OFFERED on the same run. Data, not branches.
#: codex-cli: the active MCP inventory VOIDS --output-schema (codex issue #15451), so a unit
#: asking for both is asking for something no adapter can give - report the conflict, never
#: silently drop one side.
MUTUALLY_EXCLUSIVE: tuple[tuple[str, str, str], ...] = (
    (
        "mcp.tools",
        "schema.typed_output",
        "an active MCP inventory voids --output-schema on codex-cli (issue #15451); "
        "--ignore-user-config is required for the typed path and removes the tools",
    ),
)


def negotiate(
    required: Iterable[str] | Mapping[str, Any],
    profile: CapabilityProfile,
    registry: CapabilityRegistry | None = None,
) -> Negotiation:
    """Negotiate ``required`` against ``profile``.

    ``required`` may be any iterable of capability ids. Duplicates are folded; order does not
    affect the verdict. An unrecognized id raises rather than being skipped.
    """
    reg = registry or default_registry()
    wanted: Sequence[str] = sorted(set(required))
    findings: list[SupportFinding] = []
    satisfied: list[str] = []
    for cap_id in wanted:
        cap = reg.get(cap_id)
        support = profile.support(cap_id, reg)
        if support is Support.OFFERED:
            reason = (
                f"adapter {profile.adapter_id!r} measured this capability available"
            )
            satisfied.append(cap_id)
        elif support is Support.REFUSED:
            reason = (
                f"adapter {profile.adapter_id!r} measured this capability UNAVAILABLE: "
                f"{cap.degradation_note or cap.provenance}"
            )
        else:
            reason = (
                f"adapter {profile.adapter_id!r} has never measured {cap_id!r}; "
                "UNMEASURED is not OFFERED - promote it only with a recorded probe"
            )
        findings.append(SupportFinding(cap_id, cap.criticality, support, reason))

    conflicts = tuple(
        (a, b, reason)
        for a, b, reason in MUTUALLY_EXCLUSIVE
        if a in wanted and b in wanted
    )

    blocking = [f for f in findings if f.blocks]
    degrading = [f for f in findings if f.degrades]
    if blocking or conflicts:
        verdict = NegotiationVerdict.REFUSED
    elif degrading:
        verdict = NegotiationVerdict.DEGRADED
    else:
        verdict = NegotiationVerdict.AGREED

    # Assert the POSITIVE: AGREED requires N of N confirmed OFFERED, not merely "nothing blocked".
    if verdict is NegotiationVerdict.AGREED and len(satisfied) != len(
        wanted
    ):  # pragma: no cover
        raise UnknownCapability(
            f"internal inconsistency: AGREED with {len(satisfied)} of {len(wanted)} satisfied"
        )

    return Negotiation(
        adapter_id=profile.adapter_id,
        verdict=verdict,
        findings=tuple(findings),
        conflicts=conflicts,
        registry_id=reg.registry_id,
        satisfied=tuple(satisfied),
    )
