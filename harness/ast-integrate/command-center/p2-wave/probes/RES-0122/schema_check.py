#!/usr/bin/env python3
"""Structural check for license-graph.schema.json without importing jsonschema.

Repo-root `platform/` shadows stdlib platform, which breaks jsonschema/uuid.
This checker encodes the required fields the schema declares.
"""
from __future__ import annotations

from typing import Any

REQUIRED_TOP = (
    "unit_id",
    "state",
    "sentinel",
    "report_kind",
    "question",
    "legal_disclaimer",
    "not_legal_advice",
    "obligation_table",
    "trademarked_method_handling",
    "claims",
    "control",
    "tests",
    "reviewer",
    "evidence",
    "artifacts",
)
CLASS_IDS = {
    "permissive",
    "CC-BY",
    "CC-BY-SA",
    "CC-BY-NC",
    "CC-BY-ND",
    "GPL",
    "trademarked-method",
}


def _err(path: str, msg: str) -> str:
    return f"{path}: {msg}"


def check_document(doc: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(doc, dict):
        return ["root is not an object"]
    for key in REQUIRED_TOP:
        if key not in doc:
            errors.append(_err("$", f"missing {key}"))
    if doc.get("unit_id") != "RES-0122":
        errors.append(_err("unit_id", repr(doc.get("unit_id"))))
    if doc.get("state") not in {"SUCCESS", "PARTIAL", "BLOCKED", "FAILED", "TIMEOUT", "SEVERED"}:
        errors.append(_err("state", repr(doc.get("state"))))
    sentinel = str(doc.get("sentinel") or "")
    want = (
        "SUCCESS:RES-0122 in the receipt AND a per-class obligation table "
        "with clause citations and the trademarked-method handling stated"
    )
    if want not in sentinel:
        errors.append(_err("sentinel", "catalog completion sentinel missing"))
    if doc.get("report_kind") != "license-graph":
        errors.append(_err("report_kind", repr(doc.get("report_kind"))))
    if doc.get("not_legal_advice") is not True:
        errors.append(_err("not_legal_advice", "must be true"))
    if not isinstance(doc.get("legal_disclaimer"), str) or len(doc["legal_disclaimer"]) < 40:
        errors.append(_err("legal_disclaimer", "too short"))
    if not isinstance(doc.get("question"), str) or len(doc["question"]) < 40:
        errors.append(_err("question", "too short"))

    table = doc.get("obligation_table")
    if not isinstance(table, list) or len(table) < 7:
        errors.append(_err("obligation_table", "need >=7 class rows"))
        table = []
    seen = []
    for i, row in enumerate(table):
        prefix = f"obligation_table/{i}"
        if not isinstance(row, dict):
            errors.append(_err(prefix, "not object"))
            continue
        cid = row.get("class_id")
        seen.append(cid)
        for key in (
            "class_id",
            "remaining_obligations",
            "reimplementation_is_only_permitted_route",
            "forbids_reimplementation_of_unprotected_ideas",
        ):
            if key not in row:
                errors.append(_err(prefix, f"missing {key}"))
        obs = row.get("remaining_obligations") or []
        if not isinstance(obs, list) or len(obs) < 1:
            errors.append(_err(prefix, "no remaining_obligations"))
            continue
        for j, ob in enumerate(obs):
            op = f"{prefix}/remaining_obligations/{j}"
            if not isinstance(ob, dict):
                errors.append(_err(op, "not object"))
                continue
            for key in ("id", "clause_id", "clause_quote", "capture"):
                if not str(ob.get(key) or "").strip():
                    errors.append(_err(op, f"missing {key}"))
            if len(str(ob.get("clause_quote") or "")) < 24:
                errors.append(_err(op, "clause_quote too short"))
    missing = CLASS_IDS - set(seen)
    if missing:
        errors.append(_err("obligation_table", f"missing classes {sorted(missing)}"))

    tm = doc.get("trademarked_method_handling") or {}
    if not isinstance(tm, dict) or tm.get("stated") is not True:
        errors.append(_err("trademarked_method_handling", "stated!=true"))
    if tm.get("do_not_name_the_feature") is not True:
        errors.append(_err("trademarked_method_handling", "do_not_name_the_feature"))
    if tm.get("implement_the_generic_mechanism") is not True:
        errors.append(_err("trademarked_method_handling", "implement_the_generic_mechanism"))
    if len(str(tm.get("rule") or "")) < 24:
        errors.append(_err("trademarked_method_handling.rule", "too short"))

    claims = doc.get("claims")
    if not isinstance(claims, list) or len(claims) < 7:
        errors.append(_err("claims", "need >=7"))
        claims = []
    for i, claim in enumerate(claims):
        prefix = f"claims/{i}"
        if not isinstance(claim, dict):
            errors.append(_err(prefix, "not object"))
            continue
        if len(str(claim.get("claim") or "")) < 16:
            errors.append(_err(prefix, "claim too short"))
        if claim.get("verdict") not in {"CONFIRMED", "REFUTED", "PARTIAL", "E3-SINGLE-RAIL"}:
            errors.append(_err(prefix, "bad verdict"))
        rails = claim.get("rails") or []
        if not isinstance(rails, list) or len(rails) < 2:
            errors.append(_err(prefix, "need two rails"))
            continue
        for j, rail in enumerate(rails):
            rp = f"{prefix}/rails/{j}"
            if not isinstance(rail, dict):
                errors.append(_err(rp, "not object"))
                continue
            for key in (
                "kind",
                "permalink",
                "fetch_timestamp",
                "http_status",
                "sha256",
                "capture",
            ):
                if key not in rail:
                    errors.append(_err(rp, f"missing {key}"))
            if rail.get("kind") not in {"api", "prose"}:
                errors.append(_err(rp, "kind"))
            if rail.get("http_status") != 200:
                errors.append(_err(rp, "http_status"))
            sha = str(rail.get("sha256") or "")
            if len(sha) != 64:
                errors.append(_err(rp, "sha256 length"))

    control = doc.get("control") or {}
    only = control.get("classes_where_reimplementation_is_only_permitted_route")
    if not isinstance(only, list) or len(only) < 1:
        errors.append(_err("control", "need >=1 only-permitted-route class"))
    forbid = control.get("classes_that_forbid_reimplementation_of_unprotected_ideas")
    if not isinstance(forbid, list) or len(forbid) != 0:
        errors.append(
            _err(
                "control.classes_that_forbid_reimplementation_of_unprotected_ideas",
                "must be empty: 17 USC 102(b)",
            )
        )

    tests = doc.get("tests")
    if not isinstance(tests, list) or len(tests) < 2:
        errors.append(_err("tests", "need >=2"))
    reviewer = doc.get("reviewer") or {}
    if reviewer.get("not_legal_advice") is not True:
        errors.append(_err("reviewer", "not_legal_advice"))
    if not reviewer.get("reviewer_id"):
        errors.append(_err("reviewer", "reviewer_id"))
    evidence = doc.get("evidence")
    if not isinstance(evidence, list) or len(evidence) < 4:
        errors.append(_err("evidence", "need >=4 rails"))
    artifacts = doc.get("artifacts")
    if not isinstance(artifacts, list) or len(artifacts) < 1:
        errors.append(_err("artifacts", "need >=1"))
    return errors


check_document = check_document
