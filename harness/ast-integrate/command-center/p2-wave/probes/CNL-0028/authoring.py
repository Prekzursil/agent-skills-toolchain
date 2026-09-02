"""Custom-role authoring contract the incompatible-role checker can still discharge."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
TEMPLATES = HERE / "templates.json"

REQUIRED_TOP = ("id", "obligations", "permissions", "rights", "capabilities")
REQUIRED_CAPS = (
    "authors",
    "judges",
    "votes_on",
    "may_speak",
    "may_vote",
    "may_veto",
    "may_chair",
    "may_synthesise",
)
BOOL_CAPS = (
    "may_speak",
    "may_vote",
    "may_veto",
    "may_chair",
    "may_synthesise",
)
LIST_CAPS = ("authors", "judges", "votes_on")


def load_templates() -> dict[str, Any]:
    return json.loads(TEMPLATES.read_text(encoding="utf-8"))


def template_right_union(tmpl: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for body in tmpl["templates"].values():
        out.update(body.get("rights") or [])
    return out


def check_custom_role(role: dict[str, Any], tmpl: dict[str, Any] | None = None) -> dict[str, Any]:
    tmpl = tmpl if tmpl is not None else load_templates()
    codes: list[str] = []
    if not isinstance(role, dict):
        return {"accepted": False, "codes": ["NOT_AN_OBJECT"]}
    for key in REQUIRED_TOP:
        if key not in role:
            codes.append(f"MISSING_{key.upper()}")
    caps = role.get("capabilities")
    if not isinstance(caps, dict):
        codes.append("MISSING_CAPABILITIES")
        return {"accepted": False, "codes": codes}
    for key in REQUIRED_CAPS:
        if key not in caps:
            codes.append(f"MISSING_CAP_{key.upper()}")
    for key in BOOL_CAPS:
        if key in caps and not isinstance(caps[key], bool):
            codes.append(f"CAP_{key.upper()}_NOT_BOOL")
    for key in LIST_CAPS:
        if key in caps and not isinstance(caps[key], list):
            codes.append(f"CAP_{key.upper()}_NOT_LIST")
    obligations = role.get("obligations")
    if not isinstance(obligations, list) or len(obligations) < 1:
        codes.append("EMPTY_OBLIGATIONS")
    authors = set(caps.get("authors") or []) if isinstance(caps.get("authors"), list) else set()
    judges = set(caps.get("judges") or []) if isinstance(caps.get("judges"), list) else set()
    overlap = sorted(authors & judges)
    if overlap:
        codes.append("SELF_JUDGE")
    if caps.get("may_synthesise") is True and "proposal" in authors:
        codes.append("SYNTHESISER_DRIFT")
    if caps.get("may_chair") is True and caps.get("may_vote") is True:
        rights = role.get("rights") or []
        if "casting_vote" not in rights:
            codes.append("CHAIR_SUBSTANCE_VOTE")
    allowed_rights = template_right_union(tmpl)
    allowed_rights.add("casting_vote")
    claimed = role.get("rights") if isinstance(role.get("rights"), list) else []
    extra = sorted(set(claimed) - allowed_rights)
    if extra:
        codes.append("RIGHTS_ESCALATION")
    extends = role.get("extends")
    if extends is not None:
        aliases = tmpl.get("aliases") or {}
        resolved = aliases.get(extends, extends)
        if resolved not in tmpl["templates"]:
            codes.append("UNKNOWN_EXTENDS")
    unique = []
    for c in codes:
        if c not in unique:
            unique.append(c)
    return {
        "accepted": unique == [],
        "codes": unique,
        "self_judge_kinds": overlap,
        "rights_escalation": extra,
    }


def good_custom_role() -> dict[str, Any]:
    return {
        "id": "domain-challenger",
        "extends": "critic",
        "obligations": ["produce_objection", "cite_domain_standard"],
        "permissions": ["demand_evidence"],
        "rights": ["objection_must_be_recorded"],
        "capabilities": {
            "authors": ["objection"],
            "judges": [],
            "votes_on": ["proposal"],
            "may_speak": True,
            "may_vote": True,
            "may_veto": False,
            "may_chair": False,
            "may_synthesise": False,
        },
    }


def bad_self_judge() -> dict[str, Any]:
    role = copy.deepcopy(good_custom_role())
    role["id"] = "self-judging-proposer"
    role["extends"] = "proposer"
    role["obligations"] = ["produce_proposal"]
    role["capabilities"]["authors"] = ["proposal"]
    role["capabilities"]["judges"] = ["proposal"]
    return role


def bad_missing_capabilities() -> dict[str, Any]:
    return {
        "id": "opaque-custom",
        "obligations": ["do_something"],
        "permissions": [],
        "rights": [],
    }


def bad_rights_escalation() -> dict[str, Any]:
    role = copy.deepcopy(good_custom_role())
    role["id"] = "self-granted-veto"
    role["rights"] = ["objection_must_be_recorded", "absolute_veto_no_override"]
    return role
