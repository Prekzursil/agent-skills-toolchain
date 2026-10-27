"""Governance-proposal blueprint (IMP-0244 supporting artifact)."""
from __future__ import annotations

BLUEPRINT_ID = "wf.governance.proposal"


def evaluate(subject: dict) -> dict:
    del subject
    return {"verdict": "UNKNOWN", "confidence": "none", "reason": "proposal-not-binding"}
