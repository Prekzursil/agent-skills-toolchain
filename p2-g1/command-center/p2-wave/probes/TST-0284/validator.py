"""TST-0284 five-element validator for proof-of-impossibility records.

A record that cannot be refuted is a polite word for giving up. Acceptance
requires ALL FIVE mandatory elements:
  claim_shown_unobtainable, search_space_covered, methods_attempted,
  resource_limit_reached, refuting_observation.
The refuting_observation must be OBSERVABLE IN PRINCIPLE: concrete, finitely
producible by a named experiment. Unobservable-in-principle (omniscient /
infinite) observations and observations that merely restate the claim are
rejected as circular even when the field is present.
"""
from __future__ import annotations

import re
from typing import Any

MANDATORY = [
    "claim_shown_unobtainable",
    "search_space_covered",
    "methods_attempted",
    "resource_limit_reached",
    "refuting_observation",
]

_UNOBSERVABLE = re.compile(
    r"\b(everything|all\s+future|infinite|omniscient|any\s+possible\s+future|"
    r"unknowable|every\s+conceivable|nothing\s+can\s+ever)\b",
    re.IGNORECASE,
)
_RESTATES = re.compile(
    r"\b(this\s+claim|the\s+claim|this\s+impossibility|it)\s+"
    r"(is|remains)\s+(impossible|unobtainable|refuted)\b",
    re.IGNORECASE,
)


def _blank(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, str) and not v.strip():
        return True
    if isinstance(v, (list, dict)) and not v:
        return True
    return False


def validate(record: dict[str, Any]) -> dict[str, Any]:
    missing = [f for f in MANDATORY if _blank(record.get(f))]
    refut = record.get("refuting_observation")
    circular = None
    if refut and not isinstance(refut, (list, dict)):
        text = str(refut)
        if _UNOBSERVABLE.search(text):
            circular = (
                "unobservable-in-principle: the refuting observation invokes "
                "omniscient or infinite knowledge, so no finite experiment "
                "could produce it"
            )
        elif _RESTATES.search(text):
            circular = (
                "circular: the refuting observation merely restates the "
                "claim instead of naming a producible observation"
            )
    elif isinstance(refut, (list, dict)):
        joined = " ".join(str(x) for x in refut) if isinstance(refut, list) else json_none(refut)
        if _UNOBSERVABLE.search(joined):
            circular = (
                "unobservable-in-principle: the refuting observation invokes "
                "omniscient or infinite knowledge"
            )
    accepted = not missing and circular is None
    out = {
        "accepted": accepted,
        "missing": missing,
        "circular": circular,
        "elements_present": [f for f in MANDATORY if f not in missing],
        "five_element_gate": "Acceptance requires all five elements.",
    }
    return out


def json_none(d: dict) -> str:
    try:
        import json

        return json.dumps(d)
    except Exception:
        return str(d)
