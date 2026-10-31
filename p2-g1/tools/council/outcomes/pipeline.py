"""Outcome pipeline: stages must not rewrite kind identity."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable

from council.outcomes.kinds import (
    KIND_DECISION,
    KIND_NO_DECISION,
    CollapseForbidden,
    OutcomeValidationError,
    parse_outcome,
)


def outcome_unmodified(raw: dict[str, Any], artifact: dict[str, Any]) -> bool:
    got = (artifact.get("outcome") or {})
    return got.get("kind") == raw.get("kind") and got.get("outcome_id") == raw.get("outcome_id")


def run_pipeline(
    raw: dict[str, Any],
    extra_stages: list[Callable[[dict[str, Any]], dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    parsed = parse_outcome(raw)
    envelope: dict[str, Any] = {"outcome": deepcopy(parsed), "stages": ["parse"]}
    for stage in extra_stages or []:
        envelope = stage(envelope)
        envelope.setdefault("stages", []).append(getattr(stage, "__name__", "stage"))
        kind = (envelope.get("outcome") or {}).get("kind")
        if parsed["kind"] == KIND_NO_DECISION and kind == KIND_DECISION:
            raise CollapseForbidden("NO-DECISION coerced to DECISION")
        if kind != parsed["kind"]:
            raise OutcomeValidationError(f"pipeline rewrote {parsed['kind']} -> {kind}")
    return envelope
