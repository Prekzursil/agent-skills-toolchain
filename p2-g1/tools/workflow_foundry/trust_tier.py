"""Trust-tier assignment from evidence, not from candidate labels."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

REASON_UNKNOWN_REFUSED = "unknown-tier-refused"
STATUS_AUTO_ADOPTED = "AUTO_ADOPTED"
STATUS_REFUSED = "REFUSED"
OVERRIDE_CLEAN_ROOM = "clean-room"
OVERRIDE_OWNER_APPROVAL = "owner-approval"


def classify_by_candidate_label(candidate: dict[str, Any]) -> str:
    for key in ("claimed_tier", "trust_tier", "tier"):
        val = str(candidate.get(key) or "").strip().lower()
        if val:
            return val
    return "unknown"


def _evidence_tier(evidence: dict[str, Any]) -> str:
    pub = evidence.get("publisher_identity") or {}
    sig = evidence.get("signature") or {}
    repo = evidence.get("repo_ownership") or {}
    kind = str(pub.get("kind") or repo.get("kind") or "").lower()
    verified = bool(pub.get("verified")) and bool(repo.get("verified"))
    valid = bool(sig.get("valid"))
    if kind in {"first-party", "vendor"} and verified and valid:
        return kind
    return "unknown"


@dataclass
class TierAssignment:
    tier: str
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {"tier": self.tier, "reason": self.reason}


def assign_trust_tier(candidate: dict[str, Any], evidence: dict[str, Any], **_kwargs: Any) -> TierAssignment:
    tier = _evidence_tier(evidence)
    if tier == "unknown":
        return TierAssignment(tier="unknown", reason="evidence-unverified")
    return TierAssignment(tier=tier, reason="evidence-verified")


@dataclass
class Admission:
    status: str
    admitted: bool
    auto_adopted: bool
    tier: str
    reason: str
    required_fix: str | None
    method: str = "tier-as-admission-input"

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "admitted": self.admitted,
            "auto_adopted": self.auto_adopted,
            "tier": self.tier,
            "reason": self.reason,
            "required_fix": self.required_fix,
            "method": self.method,
        }


def admit_candidate(candidate: dict[str, Any], evidence: dict[str, Any], **kwargs: Any) -> Admission:
    assignment = assign_trust_tier(candidate, evidence, **kwargs)
    if assignment.tier == "unknown":
        return Admission(
            status=STATUS_REFUSED,
            admitted=False,
            auto_adopted=False,
            tier="unknown",
            reason=REASON_UNKNOWN_REFUSED,
            required_fix="supply-verified-first-party-or-vendor-evidence",
        )
    return Admission(
        status=STATUS_AUTO_ADOPTED,
        admitted=True,
        auto_adopted=True,
        tier=assignment.tier,
        reason=assignment.reason,
        required_fix=None,
    )
