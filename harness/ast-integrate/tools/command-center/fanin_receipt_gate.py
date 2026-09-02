"""Role-aware fan-in receipt rejection gate (IMP-0425)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

DECISION_ACCEPT = "ACCEPT"
DECISION_FAILED = "FAILED"
ROLE_RECEIPT = "RECEIPT"
ROLE_RESULT = "RESULT"

_RECEIPT_OPENERS = (
    "background job",
    "in the background",
    "job id",
    "job-id",
    "codex job",
    "codex:status",
    "/codex:status",
    "status: completed",
    "fire-and-forget",
    "queued",
    "i've started this",
    "receipt",
)


@dataclass
class PhraseHit:
    phrase: str
    at: int = 0


@dataclass
class Decision:
    decision: str
    role: str
    can_satisfy_barrier: bool
    reason: str
    phrase_hits: list[PhraseHit] = field(default_factory=list)
    structured: bool = False
    opener_is_receipt_speech: bool = False


def _text(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        import json
        return json.dumps(payload)
    return str(payload)


def _is_receipt(payload: Any) -> bool:
    text = _text(payload).lower()
    if isinstance(payload, dict):
        keys = {str(k).lower() for k in payload.keys()}
        if {"job_id", "status"} <= keys or {"receipt_id", "ok"} <= keys:
            if payload.get("role") == "result" or payload.get("kind") == "analysis":
                return False
            if "analysis" in keys or "discussion" in keys or "findings" in keys:
                return False
            return True
        if payload.get("type") in {"receipt", "job-status", "background-job"}:
            return True
    opener = text.strip()[:120]
    if any(p in opener for p in _RECEIPT_OPENERS) and "analysis" not in text[:200]:
        if "discuss" in text or "mention" in text or "quoted" in text:
            return False
        return True
    if "this is a receipt" in text or "job-id:" in text:
        return True
    return False


def evaluate(payload: Any) -> Decision:
    receipt = _is_receipt(payload)
    hits = [PhraseHit(p) for p in _RECEIPT_OPENERS if p in _text(payload).lower()]
    if receipt:
        return Decision(
            decision=DECISION_FAILED,
            role=ROLE_RECEIPT,
            can_satisfy_barrier=False,
            reason="receipt-speech",
            phrase_hits=hits,
            structured=isinstance(payload, dict),
            opener_is_receipt_speech=True,
        )
    return Decision(
        decision=DECISION_ACCEPT,
        role=ROLE_RESULT,
        can_satisfy_barrier=True,
        reason="genuine-result",
        phrase_hits=hits,
        structured=isinstance(payload, dict),
        opener_is_receipt_speech=False,
    )


def admit_to_barrier(payload: Any) -> dict[str, Any]:
    d = evaluate(payload)
    admitted = d.role == ROLE_RESULT
    return {
        "admitted": admitted,
        "barrier_satisfied": admitted,
        "state": d.decision,
        "role": d.role,
    }


def naive_substring_decide(payload: Any) -> str:
    text = _text(payload).lower()
    if any(p in text for p in ("receipt", "job id", "background", "queued", "status:")):
        return DECISION_FAILED
    return DECISION_ACCEPT
