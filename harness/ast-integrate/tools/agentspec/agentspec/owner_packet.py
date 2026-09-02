"""Owner packet checker for HumanCheckpoint pauses (IMP-0218).

An owner packet is the ONE foundation-level question a paused workflow puts to
its owner, together with the recommendation, the trade-off, the default that
applies if the owner never answers, and the path of the durable record. The
checker is field-by-field and returns every defect, so a probe can tell a
two-question packet from a recommendation-less one.
"""
from __future__ import annotations

from typing import Any

REQUIRED_FIELDS: tuple[str, ...] = (
    "question",
    "recommendation",
    "tradeoff",
    "default",
    "durable_record",
)
EXPECTED_QUESTIONS = 1


def _non_blank(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def foundation_question_count(packet: dict[str, Any]) -> int:
    """How many foundation-level questions the packet asks.

    A ``questions`` list counts every non-blank entry; otherwise a non-blank
    singular ``question`` counts as one. Both present count together, so a
    packet cannot smuggle a second question past the singular field.
    """
    if not isinstance(packet, dict):
        return 0
    count = 0
    many = packet.get("questions")
    if isinstance(many, (list, tuple)):
        count += sum(1 for q in many if _non_blank(q))
    elif _non_blank(many):
        count += 1
    if _non_blank(packet.get("question")):
        count += 1
    return count


def check_owner_packet(packet: dict[str, Any]) -> list[str]:
    """Return every defect in ``packet`` (empty list == well-formed).

    Defect strings are stable identifiers: ``foundation_question_count=N expected=1``,
    ``missing_or_empty:<field>`` and ``default_not_allowed:<default>``.
    """
    if not isinstance(packet, dict):
        return ["packet_not_an_object"]
    errors: list[str] = []
    qcount = foundation_question_count(packet)
    if qcount != EXPECTED_QUESTIONS:
        errors.append(f"foundation_question_count={qcount} expected={EXPECTED_QUESTIONS}")
    for name in REQUIRED_FIELDS:
        if not _non_blank(packet.get(name)):
            errors.append(f"missing_or_empty:{name}")
    allowed = packet.get("allowed")
    if isinstance(allowed, (list, tuple)) and allowed and _non_blank(packet.get("default")):
        if packet["default"] not in allowed:
            errors.append(f"default_not_allowed:{packet['default']}")
    return errors
