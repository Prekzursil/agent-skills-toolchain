"""Legal/compliance blueprint: UNKNOWN under jurisdictional uncertainty (IMP-0244)."""
from __future__ import annotations

from typing import Any

BLUEPRINT_ID = "wf.legal-compliance.jurisdiction-unknown"
VERDICT_UNKNOWN = "UNKNOWN"
VERDICT_RULE_SATISFIED = "RULE_SATISFIED"
FORBIDDEN_CONFIDENT_VERDICTS = ("COMPLIANT", "LAWFUL", "LEGAL")
EXTERNAL_FORUMS = frozenset({"EU-GDPR", "US-CA-CCPA", "UK-GDPR"})


def jurisdiction_is_uncertain(jurisdiction: Any) -> bool:
    if not isinstance(jurisdiction, dict):
        return True
    status = str(jurisdiction.get("status") or "").lower()
    if status == "uncertain":
        return True
    conflicts = jurisdiction.get("conflicts") or []
    if isinstance(conflicts, list) and len(conflicts) > 1:
        return True
    forum = str(jurisdiction.get("forum") or "")
    if not forum:
        return True
    return False


def evaluate(subject: dict[str, Any]) -> dict[str, Any]:
    jur = subject.get("jurisdiction") if isinstance(subject, dict) else None
    if jurisdiction_is_uncertain(jur):
        return {"verdict": VERDICT_UNKNOWN, "confidence": "none", "reason": "jurisdiction-uncertain"}
    forum = str((jur or {}).get("forum") or "")
    if forum in EXTERNAL_FORUMS:
        return {"verdict": VERDICT_UNKNOWN, "confidence": "none", "reason": f"external-statute:{forum}"}
    facts = subject.get("facts") if isinstance(subject, dict) else {}
    if isinstance(facts, dict) and facts.get("retention_days_declared") is True:
        return {
            "verdict": VERDICT_RULE_SATISFIED,
            "confidence": "none",
            "reason": "internal-retention-declared",
        }
    return {"verdict": VERDICT_UNKNOWN, "confidence": "none", "reason": "unsupported"}
