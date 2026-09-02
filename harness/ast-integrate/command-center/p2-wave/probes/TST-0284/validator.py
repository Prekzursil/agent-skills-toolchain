#!/usr/bin/env python3
"""Five-element proof-of-impossibility validator (TST-0284).

A record is a proof only if it names (1) the exact claim shown unobtainable,
(2) the search space actually covered, (3) the methods attempted with their
outputs, (4) the resource limit reached, and (5) a concrete observation that
WOULD refute the impossibility. A record that cannot be refuted by any named
observation is not a proof and is rejected.

The circularity gate rejects a refuting observation that is unobservable in
principle (no finite experiment could produce it).
"""
from __future__ import annotations

import re
from typing import Any, Mapping

MANDATORY = (
    "claim_shown_unobtainable",
    "search_space_covered",
    "methods_attempted",
    "resource_limit_reached",
    "refuting_observation",
)

ALIASES = {
    "claim_shown_unobtainable": (
        "claim_shown_unobtainable",
        "claim_shown_impossible",
        "unobtainable_claim",
        "why_unobtainable",
        "exact_claim",
        "claim",
    ),
    "search_space_covered": (
        "search_space_covered",
        "search_space",
        "exhausted_sources",
        "exhaustive_domain",
        "source_classes",
        "substrates",
    ),
    "methods_attempted": (
        "methods_attempted",
        "attempts",
        "methods",
        "queries",
    ),
    "resource_limit_reached": (
        "resource_limit_reached",
        "resource_limit",
        "access_barrier",
        "missing_prerequisite",
        "limit_reached",
    ),
    "refuting_observation": (
        "refuting_observation",
        "falsifier",
        "settling_experiment",
        "named_observation",
        "overturning_observation",
    ),
}

# Unobservable-in-principle. Keep this list of *principle* barriers, not of
# ordinary "we did not see X" language — otherwise a well-formed record that
# names a finite experiment is over-blocked.
_UNOBSERVABLE = (
    re.compile(r"\bunobservable\b", re.I),
    re.compile(r"in principle undetectable", re.I),
    re.compile(r"cannot (ever )?be observed", re.I),
    re.compile(r"\bomniscient\b", re.I),
    re.compile(r"all possible worlds", re.I),
    re.compile(r"inaccessible possible world", re.I),
    re.compile(r"\binfinite (time|search|resources|attempts|evidence)\b", re.I),
    re.compile(r"if we knew everything", re.I),
    re.compile(r"no observation could", re.I),
    re.compile(r"\bineffable\b", re.I),
    re.compile(r"private mental state with no instrument", re.I),
    re.compile(r"counterfactual universe", re.I),
    re.compile(r"every possible (piece of )?evidence", re.I),
    re.compile(r"observation that this (proof|record) is (false|wrong)", re.I),
)

_UNBOUNDED_SPACE = (
    re.compile(r"^(all|every) possible\b", re.I),
    re.compile(r"\bentire universe\b", re.I),
    re.compile(r"\bunbounded\b", re.I),
    re.compile(r"\binfinite search\b", re.I),
)

_EMPTYISH = re.compile(r"^(n/?a|none|null|unknown|unspecified|impossible to specify|-)?$", re.I)

# A finite experiment has to name *where* or *how* the observation would appear.
# Snake_case identifiers (measure_corpus) are locators; \bmeasure\b does not
# match them because '_' is a word character.
_LOCATOR = re.compile(
    r"("
    r"\b(file|path|host|runner|command|stdout|stderr|exit|rc|sha256|hash|"
    r"url|http|json|log|count|probe|fixture|artifact|inventory|matrix|"
    r"sw_vers|uname|which|python|ssh|exists?|print|return|parse|fetch|"
    r"measure|compare|bytes?|line|corpus|recordings?|kernel|re-?run)\b"
    r"|[a-z][a-z0-9]*_[a-z0-9_]+"
    r"|[A-Z]{2,5}-\d{4}"
    r"|[./][\w./-]+\.(py|json|md|yml|txt|log)"
    r"|command-center/"
    r"|tools/"
    r")",
    re.I,
)


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, Mapping):
        preferred: list[str] = []
        for key in (
            "description",
            "would_falsify_if",
            "text",
            "claim",
            "name",
            "enumeration_method",
            "members",
        ):
            if key in value:
                part = _as_text(value[key])
                if part:
                    preferred.append(part)
        return "; ".join(preferred)
    if isinstance(value, (list, tuple)):
        parts = [_as_text(item) for item in value]
        return ", ".join(part for part in parts if part)
    return ""


def _pick(record: Mapping[str, Any], field: str) -> tuple[Any, bool]:
    """Return (value, field_present). present is True if any alias key exists."""
    for key in ALIASES[field]:
        if key in record:
            return record[key], True
    return None, False


def _methods_ok(value: Any) -> tuple[bool, str]:
    if not isinstance(value, list) or len(value) < 1:
        return False, "methods_attempted must be a non-empty list"
    for i, item in enumerate(value):
        if isinstance(item, str):
            if not item.strip() or _EMPTYISH.match(item.strip()):
                return False, f"methods_attempted[{i}] empty"
            continue
        if isinstance(item, Mapping):
            method = item.get("method") or item.get("name") or item.get("query")
            output = (
                item.get("output")
                if "output" in item
                else item.get("result")
                if "result" in item
                else item.get("stdout")
            )
            if not _as_text(method) or _EMPTYISH.match(_as_text(method)):
                return False, f"methods_attempted[{i}] missing method"
            if output is None or (
                isinstance(output, str)
                and (not output.strip() or _EMPTYISH.match(output.strip()))
            ):
                return False, f"methods_attempted[{i}] missing output"
            continue
        return False, f"methods_attempted[{i}] not object or string"
    return True, ""


def circular_reason(observation: str, claim: str) -> str | None:
    text = observation.strip()
    if not text or _EMPTYISH.match(text):
        return "refuting_observation empty"
    for pat in _UNOBSERVABLE:
        if pat.search(text):
            return f"unobservable-in-principle:{pat.pattern}"
    claim_s = claim.strip()
    if claim_s and text.lower() == claim_s.lower():
        return "circular:observation-equals-claim"
    if not _LOCATOR.search(text):
        return "unobservable-in-principle:no-named-instrument"
    return None


def normalize(record: Mapping[str, Any] | None) -> dict[str, Any]:
    """Project a foreign record onto the five mandatory fields."""
    if not isinstance(record, Mapping):
        return {
            "present": {k: False for k in MANDATORY},
            "values": {k: None for k in MANDATORY},
            "missing": list(MANDATORY),
        }
    present: dict[str, bool] = {}
    values: dict[str, Any] = {}
    missing: list[str] = []
    for field in MANDATORY:
        val, had = _pick(record, field)
        present[field] = had
        values[field] = val
        if not had:
            missing.append(field)
            continue
        if field == "methods_attempted":
            ok, _ = _methods_ok(val)
            if not ok:
                missing.append(field)
            continue
        text = _as_text(val)
        if not text or _EMPTYISH.match(text):
            missing.append(field)
    return {"present": present, "values": values, "missing": missing}


def validate(record: Any) -> dict[str, Any]:
    """Return accepted, reasons, missing, circular."""
    if not isinstance(record, Mapping):
        return {
            "accepted": False,
            "reasons": ["record-not-object"],
            "missing": list(MANDATORY),
            "circular": True,
            "classification": "schema-invalid",
            "present": {k: False for k in MANDATORY},
        }
    norm = normalize(record)
    missing = list(norm["missing"])
    present = norm["present"]
    values = norm["values"]
    reasons: list[str] = []

    for field in MANDATORY:
        if field not in missing:
            continue
        if present.get(field):
            reasons.append(f"empty-or-invalid:{field}")
        else:
            reasons.append(f"missing-field:{field}")

    claim = _as_text(values.get("claim_shown_unobtainable"))
    space = _as_text(values.get("search_space_covered"))
    limit = _as_text(values.get("resource_limit_reached"))
    obs = _as_text(values.get("refuting_observation"))

    if present.get("search_space_covered") and space:
        for pat in _UNBOUNDED_SPACE:
            if pat.search(space):
                reasons.append("search-space-unbounded")
                if "search_space_covered" not in missing:
                    missing.append("search_space_covered")
                break

    if present.get("resource_limit_reached") and re.search(
        r"\bunlimited\b|\binfinite\b", limit, re.I
    ):
        reasons.append("resource-limit-not-finite")
        if "resource_limit_reached" not in missing:
            missing.append("resource_limit_reached")

    circ = None
    if present.get("refuting_observation") and _as_text(values.get("refuting_observation")):
        circ = circular_reason(obs, claim)
        if circ:
            reasons.append(circ)
            # Present-but-circular is a rejection, not an absent field.

    methods_ok, methods_why = _methods_ok(values.get("methods_attempted"))
    if present.get("methods_attempted") and not methods_ok:
        tag = f"empty-or-invalid:methods_attempted:{methods_why}"
        if tag not in reasons:
            reasons.append(tag)

    seen: set[str] = set()
    ordered: list[str] = []
    for r in reasons:
        if r not in seen:
            seen.add(r)
            ordered.append(r)
    reasons = ordered

    circular = bool(circ)
    accepted = not reasons and not missing
    if accepted:
        classification = "ok"
    elif any(r == "missing-field:refuting_observation" for r in reasons):
        classification = "missing-refuting-observation"
    elif circular or any(
        "unobservable" in r or r.startswith("circular:") for r in reasons
    ):
        classification = "circular-unobservable"
    elif any(r.startswith("missing-field:") for r in reasons):
        classification = "incomplete"
    else:
        classification = "invalid"
    return {
        "accepted": accepted,
        "reasons": reasons,
        "missing": missing,
        "circular": circular,
        "classification": classification,
        "present": present,
    }


def missing_elements(record: Any) -> list[str]:
    return list(validate(record)["missing"])
