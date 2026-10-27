"""Trust-tier assignment for candidate sources + the admission gate (IMP-0158).

Each candidate is assigned ONE tier from EVIDENCE (publisher identity,
release signature, repo ownership):

  first-party  the owner's own publisher identity, on an owner-owned repo
  vendor       a verified third-party publisher identity + verified signature
  community    a verified publisher identity without a vendor-grade signature
  unknown      missing, mismatched or failed evidence of any of the above

The tier is an INPUT to admission, never a label: ``decide_admission``
refuses to AUTO-ADMIT an ``unknown``-tier candidate. An unknown candidate
reaches the registry only through an explicit owner approval token or a
clean-room reimplementation record. Determinism: tier assignment is a pure
function of the evidence mapping (sha256 over the sorted evidence keys); no
clock, no randomness, no environment reads.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Mapping

TIERS = ("first-party", "vendor", "community", "unknown")
TIER_FIRST_PARTY = "first-party"
TIER_VENDOR = "vendor"
TIER_COMMUNITY = "community"
TIER_UNKNOWN = "unknown"

AUTO_ADMIT = "AUTO-ADMIT"
REFUSED = "REFUSED"
CONDITIONAL = "CONDITIONAL-ADOPT"

#: The estate first-party publisher identity (owner). Configurable per
#: policy document; this default matches the estate publisher id.
DEFAULT_FIRST_PARTY_PUBLISHER = "prekzursil"
DEFAULT_FIRST_PARTY_REPO_PREFIX = "Prekzursil/"

EVIDENCE_KEYS = (
    "publisher_id",
    "publisher_repo",
    "identity_verified",
    "signature_verified",
    "owner_approval",
    "clean_room_reimplementation",
)


@dataclass(frozen=True)
class TierAssignment:
    tier: str
    reasons: tuple[str, ...]
    evidence_sha256: str
    ignored_fields: tuple[str, ...] = field(default=())

    def as_dict(self) -> dict[str, Any]:
        return {
            "tier": self.tier,
            "reasons": list(self.reasons),
            "evidence_sha256": self.evidence_sha256,
            "ignored_fields": list(self.ignored_fields),
        }


def _evidence_digest(evidence: Mapping[str, Any]) -> str:
    payload = {k: evidence.get(k) for k in EVIDENCE_KEYS}
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def assign_tier(candidate: Mapping[str, Any], first_party_publisher: str = DEFAULT_FIRST_PARTY_PUBLISHER) -> TierAssignment:
    """Pure tier assignment from evidence. No clock, no randomness."""
    evidence = candidate.get("trust_evidence") if isinstance(candidate.get("trust_evidence"), Mapping) else candidate
    publisher = str(evidence.get("publisher_id") or "")
    repo = str(evidence.get("publisher_repo") or "")
    identity = evidence.get("identity_verified") is True
    signature = evidence.get("signature_verified") is True
    reasons: list[str] = []

    if identity and publisher == first_party_publisher:
        if repo.startswith(DEFAULT_FIRST_PARTY_REPO_PREFIX) or not repo:
            reasons.append("publisher matches the first-party identity")
            if repo:
                reasons.append("repo " + repo + " is under the owner namespace")
            tier = TIER_FIRST_PARTY
        else:
            reasons.append("publisher matches first-party but repo " + repo + " is outside the owner namespace")
            tier = TIER_COMMUNITY if signature else TIER_UNKNOWN
    elif identity and signature:
        reasons.append("publisher identity verified" + (" for " + publisher if publisher else ""))
        reasons.append("release signature verified")
        tier = TIER_VENDOR
    elif identity:
        reasons.append("publisher identity verified" + (" for " + publisher if publisher else ""))
        reasons.append("no vendor-grade signature on the release")
        tier = TIER_COMMUNITY
    else:
        if not publisher:
            reasons.append("no publisher identity on the candidate")
        elif not identity:
            reasons.append("publisher " + publisher + " is present but NOT verified")
        reasons.append("evidence does not establish any known tier")
        tier = TIER_UNKNOWN

    known = set(EVIDENCE_KEYS) | {"trust_evidence"}
    ignored = tuple(sorted(k for k in candidate.keys() if k not in known))
    return TierAssignment(tier=tier, reasons=tuple(reasons), evidence_sha256=_evidence_digest(evidence), ignored_fields=ignored)


@dataclass(frozen=True)
class AdmissionVerdict:
    verdict: str
    tier: str
    requirements: tuple[str, ...]
    assignment: TierAssignment

    def as_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "tier": self.tier,
            "requirements": list(self.requirements),
            "assignment": self.assignment.as_dict(),
        }


def decide_admission(
    candidate: Mapping[str, Any],
    first_party_publisher: str = DEFAULT_FIRST_PARTY_PUBLISHER,
) -> AdmissionVerdict:
    """Admission consumes the tier. Unknown-tier is never auto-adopted."""
    assignment = assign_tier(candidate, first_party_publisher=first_party_publisher)
    evidence = candidate.get("trust_evidence") if isinstance(candidate.get("trust_evidence"), Mapping) else candidate
    owner_ok = evidence.get("owner_approval") is True
    clean_room = evidence.get("clean_room_reimplementation") is True

    if assignment.tier == TIER_UNKNOWN:
        if owner_ok and clean_room:
            return AdmissionVerdict(
                verdict=CONDITIONAL,
                tier=assignment.tier,
                requirements=(
                    "explicit owner approval recorded",
                    "clean-room reimplementation record attached",
                ),
                assignment=assignment,
            )
        if owner_ok:
            return AdmissionVerdict(
                verdict=CONDITIONAL,
                tier=assignment.tier,
                requirements=("explicit owner approval recorded",),
                assignment=assignment,
            )
        if clean_room:
            return AdmissionVerdict(
                verdict=CONDITIONAL,
                tier=assignment.tier,
                requirements=("clean-room reimplementation record attached",),
                assignment=assignment,
            )
        return AdmissionVerdict(
            verdict=REFUSED,
            tier=assignment.tier,
            requirements=(
                "unknown-tier candidates are never auto-adopted; they require "
                "clean-room reimplementation or explicit owner approval",
            ),
            assignment=assignment,
        )

    if assignment.tier == TIER_COMMUNITY and not owner_ok:
        return AdmissionVerdict(
            verdict=CONDITIONAL,
            tier=assignment.tier,
            requirements=("community tier admits conditionally: pass the conformance suite before publish",),
            assignment=assignment,
        )
    return AdmissionVerdict(verdict=AUTO_ADMIT, tier=assignment.tier, requirements=(), assignment=assignment)


__all__ = [
    "TIERS",
    "TIER_FIRST_PARTY",
    "TIER_VENDOR",
    "TIER_COMMUNITY",
    "TIER_UNKNOWN",
    "AUTO_ADMIT",
    "REFUSED",
    "CONDITIONAL",
    "TierAssignment",
    "AdmissionVerdict",
    "assign_tier",
    "decide_admission",
    "EVIDENCE_KEYS",
]
