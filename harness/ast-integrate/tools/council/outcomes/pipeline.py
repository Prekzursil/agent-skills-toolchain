"""Outcome pipeline: every stage must hand the parsed outcome on unmodified.

:func:`run_pipeline` validates a raw outcome with :func:`council.outcomes.kinds.parse_outcome`,
wraps it in an envelope ``{"outcome": <parsed>, "stages": ["parse", ...], "fingerprint":
<sha256>}`` and threads the envelope through the optional ``extra_stages``. After every stage
the outcome payload is compared with the parsed original over its canonical JSON, not just its
``kind`` label:

* NO-DECISION rewritten to DECISION, or any kind rewritten to a binary alias (PASS/FAIL/...),
  raises :class:`CollapseForbidden`;
* any other kind rewrite, a dropped payload, or a changed/added/removed field raises
  :class:`OutcomeValidationError` naming the fields that differ.

:func:`outcome_unmodified` is the same deep check exposed for callers that hold a raw outcome
and a final artifact.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Callable, Mapping

from .kinds import (
    KIND_DECISION,
    KIND_NO_DECISION,
    CollapseForbidden,
    OutcomeValidationError,
    parse_outcome,
)

Stage = Callable[[dict[str, Any]], dict[str, Any]]

_BINARY_ALIASES: frozenset[str] = frozenset({"FAIL", "PASS", "SUCCESS", "FAILED"})


def payload_fingerprint(outcome: Mapping[str, Any]) -> str:
    """SHA-256 over the canonical JSON (sorted keys, compact separators) of an outcome payload."""
    canonical = json.dumps(
        outcome, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def outcome_unmodified(raw: Mapping[str, Any], artifact: Mapping[str, Any]) -> bool:
    """True when ``artifact["outcome"]`` is ``raw`` field for field (kind and id included)."""
    if not isinstance(raw, Mapping) or not isinstance(artifact, Mapping):
        return False
    got = artifact.get("outcome")
    if not isinstance(got, Mapping):
        return False
    if got.get("kind") != raw.get("kind") or got.get("outcome_id") != raw.get("outcome_id"):
        return False
    return payload_fingerprint(got) == payload_fingerprint(raw)


def _changed_fields(expected: Mapping[str, Any], got: Mapping[str, Any]) -> list[str]:
    return sorted(
        key
        for key in set(expected) | set(got)
        if key not in expected or key not in got or expected[key] != got[key]
    )


def _check_identity(parsed: Mapping[str, Any], envelope: Any, stage_name: str) -> None:
    """Raise unless ``envelope`` still carries ``parsed`` unmodified."""
    if not isinstance(envelope, dict):
        raise OutcomeValidationError(
            f"stage {stage_name} returned {type(envelope).__name__}, not an envelope dict"
        )
    got = envelope.get("outcome")
    if not isinstance(got, Mapping):
        raise OutcomeValidationError(f"stage {stage_name} dropped the outcome payload")
    expected_kind = parsed["kind"]
    kind = got.get("kind")
    if kind != expected_kind:
        if expected_kind == KIND_NO_DECISION and kind == KIND_DECISION:
            raise CollapseForbidden(f"stage {stage_name} coerced NO-DECISION to DECISION")
        if str(kind or "").strip().upper() in _BINARY_ALIASES:
            raise CollapseForbidden(
                f"stage {stage_name} collapsed {expected_kind} into binary {kind}"
            )
        raise OutcomeValidationError(f"stage {stage_name} rewrote kind {expected_kind} -> {kind}")
    if payload_fingerprint(got) != payload_fingerprint(parsed):
        raise OutcomeValidationError(
            f"stage {stage_name} modified outcome fields {_changed_fields(parsed, got)}"
        )


def run_pipeline(
    raw: Mapping[str, Any],
    extra_stages: list[Stage] | None = None,
) -> dict[str, Any]:
    """Parse ``raw`` and thread the envelope through ``extra_stages`` with identity checks.

    Each stage receives the envelope and returns the (possibly enriched) envelope; it may add
    envelope-level keys but the ``outcome`` payload must come back byte-identical. The stage
    name (``__name__``) is appended to ``stages`` only after its output passed the check.
    """
    if not isinstance(raw, Mapping):
        raise OutcomeValidationError("outcome is not an object")
    parsed = parse_outcome(dict(raw))
    expected = payload_fingerprint(parsed)
    envelope: dict[str, Any] = {
        "outcome": deepcopy(parsed),
        "stages": ["parse"],
        "fingerprint": expected,
    }
    for stage in extra_stages or []:
        name = getattr(stage, "__name__", None) or "stage"
        envelope = stage(envelope)
        _check_identity(parsed, envelope, name)
        stages = envelope.setdefault("stages", [])
        if not isinstance(stages, list):
            raise OutcomeValidationError(f"stage {name} replaced the stage log with {type(stages).__name__}")
        stages.append(name)
        envelope["fingerprint"] = expected
    envelope["identity_verified"] = True
    return envelope


__all__ = ["Stage", "outcome_unmodified", "payload_fingerprint", "run_pipeline"]
