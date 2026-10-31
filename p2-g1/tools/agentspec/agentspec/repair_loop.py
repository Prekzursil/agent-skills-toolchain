"""RepairLoop node with attempt limit and proof-of-impossibility terminal."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class PassedTerminal:
    record_type: str = "repair_passed"
    attempts_used: int = 0
    max_attempts: int = 0
    exhausted: bool = False
    proof: dict | None = None


@dataclass
class AttemptLimitTerminal:
    record_type: str = "repair_attempt_limit"
    attempts_used: int = 0
    max_attempts: int = 0
    exhausted: bool = True
    proof: dict | None = None


@dataclass
class ProvedImpossibleTerminal:
    record_type: str = "repair_proved_impossible"
    attempts_used: int = 0
    max_attempts: int = 0
    exhausted: bool = False
    proof: dict | None = None


def terminal_as_dict(term: Any) -> dict[str, Any]:
    return {
        "record_type": getattr(term, "record_type", None),
        "attempts_used": getattr(term, "attempts_used", None),
        "max_attempts": getattr(term, "max_attempts", None),
        "exhausted": getattr(term, "exhausted", None),
        "proof": getattr(term, "proof", None),
    }


def run_fixture(doc: dict[str, Any]) -> Any:
    max_attempts = int(doc.get("max_attempts") or 0)
    attempts = list(doc.get("attempts") or [])
    proof = doc.get("proof") if isinstance(doc.get("proof"), dict) else doc.get("impossibility")
    if proof is None and isinstance(doc.get("proof_of_impossibility"), dict):
        proof = doc["proof_of_impossibility"]
    for step in attempts:
        if isinstance(step, dict) and isinstance(step.get("proof"), dict):
            proof = step["proof"]
            break
    if isinstance(proof, dict) and proof.get("settling_experiment"):
        used = min(len(attempts), max_attempts) if attempts else 1
        return ProvedImpossibleTerminal(
            attempts_used=used,
            max_attempts=max_attempts,
            exhausted=False,
            proof=proof,
        )
    passed_at = None
    for i, step in enumerate(attempts, 1):
        if isinstance(step, dict) and step.get("review_passed"):
            passed_at = i
            break
    if passed_at is not None:
        return PassedTerminal(attempts_used=passed_at, max_attempts=max_attempts, exhausted=False)
    used = len(attempts) if attempts else max_attempts
    return AttemptLimitTerminal(attempts_used=max_attempts, max_attempts=max_attempts, exhausted=True)
