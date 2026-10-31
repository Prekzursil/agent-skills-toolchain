"""Blueprint registry for IMP-0244 security blueprints 5-8."""
from __future__ import annotations

from dataclasses import dataclass

from .legal_compliance import BLUEPRINT_ID as LEGAL_ID
from .policy_as_code import POLICY_ID


@dataclass(frozen=True)
class Blueprint:
    id: str
    kind: str


def load_all() -> list[Blueprint]:
    return [
        Blueprint(id=POLICY_ID, kind="policy-as-code"),
        Blueprint(id=LEGAL_ID, kind="legal-compliance"),
        Blueprint(id="wf.privacy.retention-declared", kind="privacy"),
        Blueprint(id="wf.governance.proposal", kind="governance-proposal"),
    ]
