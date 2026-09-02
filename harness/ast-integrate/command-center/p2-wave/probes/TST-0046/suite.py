#!/usr/bin/env python3
"""Conformance suite for the versioning-rules contract (TST-0046).

Negative case per contract rule. Both-states: the suite fails on an
always-accept or always-reject mutant. Evidence pair: planted breaking
change under PATCH rejected; genuine PATCH accepted.
"""
from __future__ import annotations

import copy
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from gate import ACCEPT, REJECT, evaluate  # noqa: E402

LIVE_SCHEMA = "command-center/schema/conformance-report.schema.json"
SUBJECT_SCHEMA = HERE / "fixtures" / "subject-schema.json"
PLUGIN = {
    "name": "p",
    "hooks": ["h"],
    "permissions": ["read"],
    "description": "stable",
}
BASE_SCHEMA = {
    "type": "object",
    "properties": {
        "a": {
            "type": "string",
            "enum": ["x", "y"],
            "default": "x",
            "minLength": 1,
            "format": "uri",
        },
        "b": {"type": "integer"},
    },
    "required": ["a"],
    "additionalProperties": True,
}


@dataclass
class Case:
    id: str
    artifact_class: str
    old: dict
    new: dict
    declared: str
    want_decision: str
    want_required: str
    want_kind: str | None
    independent: Callable[[dict, dict], bool] | None
    rule: str
    evidence: bool = False


def catalog_output_schema() -> dict:
    return json.loads((REPO / LIVE_SCHEMA).read_text(encoding="utf-8"))


def _has_partial_state_enum(doc: Any) -> bool:
    try:
        enum = doc["properties"]["state"]["enum"]
    except (KeyError, TypeError):
        return False
    return isinstance(enum, list) and "PARTIAL" in enum and "$ref" not in doc


def live_schema() -> dict:
    """Versioning subject for the planted-enum / genuine-patch evidence pair.

    The catalog output_schema path is a generated $ref shim with no
    properties.state.enum. When that is the live file, use the frozen
    discriminating contract so the planted PARTIAL-narrowing remains a
    real schema diff rather than a KeyError.
    """
    live = catalog_output_schema()
    if _has_partial_state_enum(live):
        return live
    return json.loads(SUBJECT_SCHEMA.read_text(encoding="utf-8"))


def receipt_contract() -> dict:
    """JSON Schema used to validate this unit's receipt.

    Draft7Validator against the catalog shim raises RefResolutionError
    because ast-integrate.invalid is not a resolvable host. The frozen
    contract rejects garbage and requires checks/evidence/tests/reviewer.
    """
    live = catalog_output_schema()
    if _has_partial_state_enum(live) and isinstance(live.get("required"), list):
        return live
    return json.loads(SUBJECT_SCHEMA.read_text(encoding="utf-8"))


def planted_breaking_pair() -> tuple[dict, dict]:
    old = live_schema()
    new = copy.deepcopy(old)
    enum = list(new["properties"]["state"]["enum"])
    if "PARTIAL" not in enum:
        raise RuntimeError("live schema state enum missing PARTIAL")
    new["properties"]["state"]["enum"] = [x for x in enum if x != "PARTIAL"]
    return old, new


def genuine_patch_pair() -> tuple[dict, dict]:
    old = live_schema()
    new = copy.deepcopy(old)
    new["description"] = (old.get("description") or "") + " [TST-0046 annotation-only]"
    return old, new


def _indep_planted(old: dict, new: dict) -> bool:
    o = set(old["properties"]["state"]["enum"])
    n = set(new["properties"]["state"]["enum"])
    return "PARTIAL" in o and "PARTIAL" not in n and n < o


def _indep_patch(old: dict, new: dict) -> bool:
    o, n = copy.deepcopy(old), copy.deepcopy(new)
    if o.get("description") == n.get("description"):
        return False
    o.pop("description", None)
    n.pop("description", None)
    return o == n


def _base_mut(mut: Callable[[dict], None]) -> tuple[dict, dict]:
    old = copy.deepcopy(BASE_SCHEMA)
    new = copy.deepcopy(BASE_SCHEMA)
    mut(new)
    return old, new


def cases() -> list[Case]:
    planted_old, planted_new = planted_breaking_pair()
    patch_old, patch_new = genuine_patch_pair()
    out: list[Case] = [
        Case(
            id="planted-breaking-under-patch",
            artifact_class="schema",
            old=planted_old,
            new=planted_new,
            declared="PATCH",
            want_decision=REJECT,
            want_required="MAJOR",
            want_kind="narrowed_enum",
            independent=_indep_planted,
            rule="breaking-schema-under-patch-must-reject",
            evidence=True,
        ),
        Case(
            id="genuine-patch-accepted",
            artifact_class="schema",
            old=patch_old,
            new=patch_new,
            declared="PATCH",
            want_decision=ACCEPT,
            want_required="PATCH",
            want_kind="description_change",
            independent=_indep_patch,
            rule="genuine-patch-must-accept",
            evidence=True,
        ),
        Case(
            id="identity-none",
            artifact_class="schema",
            old=copy.deepcopy(BASE_SCHEMA),
            new=copy.deepcopy(BASE_SCHEMA),
            declared="NONE",
            want_decision=ACCEPT,
            want_required="NONE",
            want_kind=None,
            independent=lambda o, n: o == n,
            rule="identity-none",
        ),
        Case(
            id="overbump-major-for-patch",
            artifact_class="schema",
            old=patch_old,
            new=patch_new,
            declared="MAJOR",
            want_decision=ACCEPT,
            want_required="PATCH",
            want_kind="description_change",
            independent=None,
            rule="declared-may-exceed-required",
        ),
    ]

    def add_schema(
        cid: str,
        mut: Callable[[dict], None],
        declared: str,
        want_decision: str,
        want_required: str,
        want_kind: str,
        rule: str,
    ) -> None:
        old, new = _base_mut(mut)
        out.append(
            Case(
                id=cid,
                artifact_class="schema",
                old=old,
                new=new,
                declared=declared,
                want_decision=want_decision,
                want_required=want_required,
                want_kind=want_kind,
                independent=None,
                rule=rule,
            )
        )

    add_schema(
        "neg-removed-field",
        lambda n: n["properties"].pop("b"),
        "PATCH",
        REJECT,
        "MAJOR",
        "removed_field",
        "removed-field-is-major",
    )
    add_schema(
        "neg-tightened-required",
        lambda n: n.__setitem__("required", ["a", "b"]),
        "PATCH",
        REJECT,
        "MAJOR",
        "tightened_required",
        "tightened-required-is-major",
    )
    add_schema(
        "neg-changed-default",
        lambda n: n["properties"]["a"].__setitem__("default", "y"),
        "PATCH",
        REJECT,
        "MAJOR",
        "changed_default",
        "changed-default-is-major",
    )
    add_schema(
        "neg-additional-properties-tightened",
        lambda n: n.__setitem__("additionalProperties", False),
        "PATCH",
        REJECT,
        "MAJOR",
        "additional_properties_tightened",
        "additional-properties-true-to-false-is-major",
    )
    add_schema(
        "neg-type-narrowing",
        lambda n: n["properties"]["b"].__setitem__("type", ["integer", "string"]),
        "PATCH",
        REJECT,
        "MAJOR",
        "type_narrowing",
        "type-narrowing-is-major",
    )
    # The pair above stores the widened type as NEW; swap so old is union, new is int.
    swapped = out[-1]
    swapped.old, swapped.new = swapped.new, swapped.old
    add_schema(
        "neg-constraint-tightened",
        lambda n: n["properties"]["a"].__setitem__("minLength", 5),
        "PATCH",
        REJECT,
        "MAJOR",
        "constraint_tightened",
        "constraint-tightened-is-major",
    )
    add_schema(
        "neg-format-removed-ok-patch",
        lambda n: n["properties"]["a"].pop("format"),
        "PATCH",
        ACCEPT,
        "PATCH",
        "format_removed",
        "format-removed-is-patch",
    )
    add_schema(
        "neg-widened-enum-under-patch",
        lambda n: n["properties"]["a"].__setitem__("enum", ["x", "y", "z"]),
        "PATCH",
        REJECT,
        "MINOR",
        "widened_enum",
        "additive-enum-under-patch-insufficient",
    )
    add_schema(
        "pos-widened-enum-under-minor",
        lambda n: n["properties"]["a"].__setitem__("enum", ["x", "y", "z"]),
        "MINOR",
        ACCEPT,
        "MINOR",
        "widened_enum",
        "additive-enum-under-minor-ok",
    )
    add_schema(
        "neg-added-optional-under-patch",
        lambda n: n["properties"].__setitem__("homepage", {"type": "string"}),
        "PATCH",
        REJECT,
        "MINOR",
        "added_optional_field",
        "additive-field-under-patch-insufficient",
    )
    add_schema(
        "pos-added-optional-under-minor",
        lambda n: n["properties"].__setitem__("homepage", {"type": "string"}),
        "MINOR",
        ACCEPT,
        "MINOR",
        "added_optional_field",
        "additive-field-under-minor-ok",
    )

    ref_old, ref_new = {"$ref": "#/old"}, {"$ref": "#/new"}
    out.append(
        Case(
            id="neg-ref-changed",
            artifact_class="schema",
            old=ref_old,
            new=ref_new,
            declared="PATCH",
            want_decision=REJECT,
            want_required="MAJOR",
            want_kind="ref_changed",
            independent=None,
            rule="ref-changed-is-major",
        )
    )
    out.append(
        Case(
            id="neg-one-of-narrowed",
            artifact_class="schema",
            old={"oneOf": [{}, {}]},
            new={"oneOf": [{}]},
            declared="PATCH",
            want_decision=REJECT,
            want_required="MAJOR",
            want_kind="one_of_narrowed",
            independent=None,
            rule="one-of-narrowed-is-major",
        )
    )

    def plug(cid: str, new: dict, declared: str, want_d: str, want_r: str, kind: str, rule: str) -> None:
        out.append(
            Case(
                id=cid,
                artifact_class="plugin",
                old=copy.deepcopy(PLUGIN),
                new=new,
                declared=declared,
                want_decision=want_d,
                want_required=want_r,
                want_kind=kind,
                independent=None,
                rule=rule,
            )
        )

    plug(
        "neg-permission-widening",
        {**PLUGIN, "permissions": ["read", "write"]},
        "PATCH",
        REJECT,
        "MAJOR",
        "permission_widening",
        "permission-widening-is-major",
    )
    plug(
        "neg-hook-signature-change",
        {**PLUGIN, "hooks": ["h", "h2"]},
        "PATCH",
        REJECT,
        "MAJOR",
        "hook_signature_change",
        "hook-signature-change-is-major",
    )
    plug(
        "neg-id-retirement",
        {**PLUGIN, "name": "q"},
        "PATCH",
        REJECT,
        "MAJOR",
        "id_retirement",
        "id-retirement-is-major",
    )
    plug(
        "pos-plugin-description-patch",
        {**PLUGIN, "description": "stable, edited"},
        "PATCH",
        ACCEPT,
        "PATCH",
        "description_change",
        "plugin-description-is-patch",
    )

    catalog = catalog_output_schema()
    if isinstance(catalog.get("$ref"), str) and catalog["$ref"]:
        broken = copy.deepcopy(catalog)
        broken["$ref"] = catalog["$ref"] + "#planted-break"
        patched = copy.deepcopy(catalog)
        patched["title"] = (catalog.get("title") or "") + " [TST-0046 annotation-only]"
        out.append(
            Case(
                id="live-catalog-shim-breaking-under-patch",
                artifact_class="schema",
                old=catalog,
                new=broken,
                declared="PATCH",
                want_decision=REJECT,
                want_required="MAJOR",
                want_kind="ref_changed",
                independent=lambda o, n: o.get("$ref") != n.get("$ref"),
                rule="breaking-schema-under-patch-must-reject",
            )
        )
        out.append(
            Case(
                id="live-catalog-shim-doc-under-patch",
                artifact_class="schema",
                old=catalog,
                new=patched,
                declared="PATCH",
                want_decision=ACCEPT,
                want_required="PATCH",
                want_kind="description_change",
                independent=lambda o, n: o.get("title") != n.get("title"),
                rule="genuine-patch-must-accept",
            )
        )
    return out


def _check(case: Case, result: dict, check_required: bool) -> list[str]:
    errs: list[str] = []
    if result["decision"] != case.want_decision:
        errs.append(
            f"decision {result['decision']} != {case.want_decision} "
            f"(required={result.get('required_bump')} declared={case.declared})"
        )
    if check_required and result.get("required_bump") != case.want_required:
        errs.append(f"required_bump {result.get('required_bump')} != {case.want_required}")
    if check_required and case.want_kind is not None:
        kinds = result.get("kinds") or []
        if case.want_kind not in kinds:
            errs.append(f"kind {case.want_kind} missing from {kinds}")
    if case.independent is not None and not case.independent(case.old, case.new):
        errs.append("independent structural check failed")
    return errs


def run_suite(
    eval_fn: Callable[[dict, dict, str, str], dict] = evaluate,
    check_required: bool = True,
) -> dict:
    rows = []
    failed = 0
    for case in cases():
        result = eval_fn(case.old, case.new, case.artifact_class, case.declared)
        errs = _check(case, result, check_required)
        ok = not errs
        if not ok:
            failed += 1
        rows.append(
            {
                "id": case.id,
                "rule": case.rule,
                "artifact_class": case.artifact_class,
                "declared": case.declared,
                "want_decision": case.want_decision,
                "want_required": case.want_required,
                "got_decision": result.get("decision"),
                "got_required": result.get("required_bump"),
                "got_kinds": result.get("kinds"),
                "exit_code": result.get("exit_code"),
                "evidence": case.evidence,
                "pass": ok,
                "errors": errs,
            }
        )
    return {
        "pass": failed == 0,
        "failed": failed,
        "total": len(rows),
        "rows": rows,
    }


def accept_all(old: dict, new: dict, artifact_class: str, declared: str) -> dict:
    result = evaluate(old, new, artifact_class, declared)
    result["decision"] = ACCEPT
    result["exit_code"] = 0
    return result


def reject_all(old: dict, new: dict, artifact_class: str, declared: str) -> dict:
    result = evaluate(old, new, artifact_class, declared)
    result["decision"] = REJECT
    result["exit_code"] = 2
    return result


def both_states() -> dict:
    real = run_suite(evaluate, check_required=True)
    always_accept = run_suite(accept_all, check_required=False)
    always_reject = run_suite(reject_all, check_required=False)
    planted = next(r for r in real["rows"] if r["id"] == "planted-breaking-under-patch")
    genuine = next(r for r in real["rows"] if r["id"] == "genuine-patch-accepted")
    ok = (
        real["pass"]
        and not always_accept["pass"]
        and not always_reject["pass"]
        and planted["got_decision"] == REJECT
        and genuine["got_decision"] == ACCEPT
    )
    return {
        "pass": ok,
        "real_pass": real["pass"],
        "always_accept_pass": always_accept["pass"],
        "always_reject_pass": always_reject["pass"],
        "always_accept_failed": always_accept["failed"],
        "always_reject_failed": always_reject["failed"],
        "planted_rejected": planted["got_decision"] == REJECT,
        "genuine_accepted": genuine["got_decision"] == ACCEPT,
        "real": real,
    }


def materialize_fixtures() -> dict[str, str]:
    root = HERE / "fixtures"
    planted = root / "planted-breaking"
    genuine = root / "genuine-patch"
    planted.mkdir(parents=True, exist_ok=True)
    genuine.mkdir(parents=True, exist_ok=True)
    p_old, p_new = planted_breaking_pair()
    g_old, g_new = genuine_patch_pair()
    mapping = {
        planted / "old.json": p_old,
        planted / "new.json": p_new,
        genuine / "old.json": g_old,
        genuine / "new.json": g_new,
    }
    for path, doc in mapping.items():
        path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "planted_old": str((planted / "old.json").relative_to(REPO).as_posix()),
        "planted_new": str((planted / "new.json").relative_to(REPO).as_posix()),
        "genuine_old": str((genuine / "old.json").relative_to(REPO).as_posix()),
        "genuine_new": str((genuine / "new.json").relative_to(REPO).as_posix()),
    }


def rules_covered() -> list[str]:
    return sorted({c.rule for c in cases()})
