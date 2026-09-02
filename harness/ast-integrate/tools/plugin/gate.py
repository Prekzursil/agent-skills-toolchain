"""Act gate for divergence decision packets (IMP-0036).

A packet's *recommendation* is advisory: it can name an action but can never
authorise one.  For a ``DIVERGED`` file -- both copies carry lines the other
lacks -- any action needs a *recorded owner decision* on the packet, and the
requested action must be the recorded choice.  One-sided classes (``REPO-AHEAD``,
``LIVE-AHEAD``, ``IDENTICAL*``) lose nothing whichever side wins, so a known
action passes without a decision.

The gate never mutates the packet it inspects.
"""
from __future__ import annotations

from typing import Any

from plugin.drift import CLASSES, DIVERGED

REFUSE_NO_DECISION = "REFUSE-NO-RECORDED-DECISION"
REFUSE_DECISION_MISMATCH = "REFUSE-DECISION-MISMATCH"
REFUSE_UNKNOWN_ACTION = "REFUSE-UNKNOWN-ACTION"
REFUSE_UNKNOWN_CLASSIFICATION = "REFUSE-UNKNOWN-CLASSIFICATION"

TAKE_LIVE = "TAKE-LIVE"
TAKE_REPO = "TAKE-REPO"
KEEP_BOTH = "KEEP-BOTH"
NO_OP = "NO-OP"
ACTIONS: tuple[str, ...] = (TAKE_LIVE, TAKE_REPO, KEEP_BOTH, NO_OP)

RECORDED = "RECORDED"
UNRECORDED = "UNRECORDED"
DECISION_KIND = "recorded-owner-decision"

AUTHORISED_BY_DECISION = "recorded-owner-decision"
AUTHORISED_BY_CLASS = "one-sided-classification"


def _decision(packet: dict[str, Any]) -> dict[str, Any]:
    decision = packet.get("decision")
    return decision if isinstance(decision, dict) else {}


def has_recorded_decision(packet: dict[str, Any]) -> bool:
    """True when the packet carries an owner decision with ``status == RECORDED``.

    Only the ``decision`` block counts.  The ``recommendation`` block is never
    consulted, whatever action it names.
    """
    decision = _decision(packet)
    return decision.get("kind") == DECISION_KIND and decision.get("status") == RECORDED


def recorded_choice(packet: dict[str, Any]) -> str | None:
    """Return the recorded owner choice, or ``None`` when nothing is recorded."""
    if not has_recorded_decision(packet):
        return None
    choice = _decision(packet).get("choice")
    return str(choice) if choice is not None else None


def _verdict(
    packet: dict[str, Any],
    action: str,
    *,
    ok: bool,
    reason: str | None,
    authorised_by: str | None,
) -> dict[str, Any]:
    return {
        "ok": ok,
        "refused": not ok,
        "reason": reason,
        "action": action,
        "path": packet.get("path"),
        "classification": packet.get("classification"),
        "authorised_by": authorised_by,
        "recorded_choice": recorded_choice(packet),
        "recommendation_consulted": False,
    }


def act(packet: dict[str, Any], action: str) -> dict[str, Any]:
    """Decide whether ``action`` may be applied to the file ``packet`` describes.

    Returns a verdict dict with ``ok``/``refused`` (always complementary),
    ``reason`` (``None`` when allowed, else one of the ``REFUSE_*`` codes),
    the echoed ``action``, ``path`` and ``classification``, ``authorised_by``
    and the ``recorded_choice`` that was honoured.

    * unknown action -> ``REFUSE_UNKNOWN_ACTION``;
    * classification outside :data:`plugin.drift.CLASSES` ->
      ``REFUSE_UNKNOWN_CLASSIFICATION`` (nothing is known about the loss);
    * ``DIVERGED`` without a recorded decision -> ``REFUSE_NO_DECISION``;
    * ``DIVERGED`` with a recorded decision naming a different action ->
      ``REFUSE_DECISION_MISMATCH``;
    * ``DIVERGED`` with a matching recorded decision -> allowed;
    * any other class -> allowed on the strength of the classification alone.
    """
    action = str(action)
    if action not in ACTIONS:
        return _verdict(packet, action, ok=False, reason=REFUSE_UNKNOWN_ACTION, authorised_by=None)
    klass = packet.get("classification")
    if klass not in CLASSES:
        return _verdict(
            packet, action, ok=False, reason=REFUSE_UNKNOWN_CLASSIFICATION, authorised_by=None
        )
    if klass != DIVERGED:
        return _verdict(packet, action, ok=True, reason=None, authorised_by=AUTHORISED_BY_CLASS)
    if not has_recorded_decision(packet):
        return _verdict(packet, action, ok=False, reason=REFUSE_NO_DECISION, authorised_by=None)
    if recorded_choice(packet) != action:
        return _verdict(
            packet, action, ok=False, reason=REFUSE_DECISION_MISMATCH, authorised_by=None
        )
    return _verdict(packet, action, ok=True, reason=None, authorised_by=AUTHORISED_BY_DECISION)


__all__ = [
    "ACTIONS",
    "AUTHORISED_BY_CLASS",
    "AUTHORISED_BY_DECISION",
    "DECISION_KIND",
    "KEEP_BOTH",
    "NO_OP",
    "RECORDED",
    "REFUSE_DECISION_MISMATCH",
    "REFUSE_NO_DECISION",
    "REFUSE_UNKNOWN_ACTION",
    "REFUSE_UNKNOWN_CLASSIFICATION",
    "TAKE_LIVE",
    "TAKE_REPO",
    "UNRECORDED",
    "act",
    "has_recorded_decision",
    "recorded_choice",
]
