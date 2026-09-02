"""Waiver discipline: unsatisfiable conditions close only by owner record.

Never by reinterpretation, silent rewrite, or unmarked NOT-APPLICABLE.
"""
from __future__ import annotations

from typing import Any

ALLOWED_CLOSE = frozenset({"OWNER_WAIVER", "OWNER_EQUIVALENT_FORMULATION"})
FORBIDDEN_CLOSE = frozenset(
    {
        "REINTERPRETATION",
        "SILENT_REWRITE",
        "NOT_APPLICABLE_WITHOUT_JUSTIFICATION",
        "INHERITED_PHASE_GRAPH",
    }
)

RULE = (
    "An unsatisfiable-as-written stopping condition may only be closed by an "
    "owner-recorded waiver or an owner-recorded equivalent formulation. "
    "Reinterpreting the predicate (for example reading 'canary' as 'PR') is "
    "forbidden. Marking NOT-APPLICABLE without a recorded owner justification "
    "is forbidden. Inheriting PHASE-GRAPH.json is not a close."
)

REQUIRED_OWNER_FIELDS = (
    "id",
    "state",
    "answer",
    "answer_detail",
    "answered_on",
    "answer_provenance",
)


def owner_record_complete(rec: dict | None) -> tuple[bool, str]:
    if not isinstance(rec, dict):
        return False, "owner record missing"
    missing = [k for k in REQUIRED_OWNER_FIELDS if not rec.get(k)]
    if missing:
        return False, "owner record missing fields: " + ",".join(missing)
    if str(rec.get("state") or "").upper() != "ANSWERED":
        return False, "owner record is not ANSWERED"
    return True, "ok"


def attempt_close(
    *,
    condition_id: int,
    as_written: str,
    method: str,
    owner_record: dict | None,
    rewritten_text: str | None = None,
) -> dict[str, Any]:
    """Evaluate one close attempt. Does not mutate program state."""
    method_u = str(method or "").upper()
    out: dict[str, Any] = {
        "condition_id": condition_id,
        "as_written": as_written,
        "method": method_u,
        "accepted": False,
        "reason": "",
    }
    if as_written != "UNSATISFIABLE-AS-WRITTEN":
        out["reason"] = "waiver-discipline applies only to unsatisfiable-as-written"
        return out
    if method_u in FORBIDDEN_CLOSE:
        out["reason"] = (
            f"forbidden close method {method_u}: unsatisfiable may not be "
            "closed by reinterpretation, silent rewrite, unmarked N/A, or "
            "inherited phase-graph"
        )
        return out
    if method_u not in ALLOWED_CLOSE:
        out["reason"] = f"unknown close method {method_u}"
        return out
    ok, why = owner_record_complete(owner_record)
    if not ok:
        out["reason"] = why
        return out
    rec = owner_record or {}
    if method_u == "OWNER_WAIVER":
        ans = str(rec.get("answer") or "").upper()
        if "WAIVE" not in ans and "WAIVER" not in str(rec.get("text") or "").upper():
            out["reason"] = "OWNER_WAIVER record does not state a waiver"
            return out
        out["accepted"] = True
        out["reason"] = f"accepted OWNER_WAIVER via {rec.get('id')}"
        return out
    # OWNER_EQUIVALENT_FORMULATION
    detail = str(rec.get("answer_detail") or "").lower()
    has_substitute = (
        "stand" in detail
        and "canary" in detail
        and ("install" in detail or "rollback" in detail)
    )
    if not has_substitute:
        out["reason"] = (
            "OWNER_EQUIVALENT_FORMULATION record does not name a substitute "
            "pass condition"
        )
        return out
    if rewritten_text and "canary" not in rewritten_text.lower():
        out["reason"] = (
            "equivalent formulation must not erase the as-written predicate; "
            "record a substitute beside UNSATISFIABLE-AS-WRITTEN"
        )
        return out
    out["accepted"] = True
    out["reason"] = f"accepted OWNER_EQUIVALENT_FORMULATION via {rec.get('id')}"
    out["equivalent_keeps_as_written"] = True
    return out


def run_controls(oq9: dict) -> dict:
    """Known-good and known-bad close attempts."""
    planted_waiver = {
        "id": "OQ-SYN-ARC-0097-WAIVER",
        "state": "ANSWERED",
        "text": "Waive planted unsatisfiable condition SC-SYN for probe2.",
        "answer": "WAIVED.",
        "answer_detail": (
            "Fixture-only owner-recorded waiver of a planted condition. "
            "Not a program waiver of SC-13."
        ),
        "answered_on": "2026-08-24",
        "answer_provenance": "ARC-0097 probe2 fixture; not a production ruling",
    }
    incomplete = {
        "id": "OQ-SYN-INCOMPLETE",
        "state": "ANSWERED",
        "answer": "WAIVED.",
        "answer_detail": "missing answered_on and provenance",
    }
    cases = [
        attempt_close(
            condition_id=13,
            as_written="UNSATISFIABLE-AS-WRITTEN",
            method="REINTERPRETATION",
            owner_record=None,
        ),
        attempt_close(
            condition_id=13,
            as_written="UNSATISFIABLE-AS-WRITTEN",
            method="SILENT_REWRITE",
            owner_record=oq9,
            rewritten_text="PR merge succeeds",
        ),
        attempt_close(
            condition_id=13,
            as_written="UNSATISFIABLE-AS-WRITTEN",
            method="NOT_APPLICABLE_WITHOUT_JUSTIFICATION",
            owner_record=None,
        ),
        attempt_close(
            condition_id=13,
            as_written="UNSATISFIABLE-AS-WRITTEN",
            method="INHERITED_PHASE_GRAPH",
            owner_record=oq9,
        ),
        attempt_close(
            condition_id=13,
            as_written="UNSATISFIABLE-AS-WRITTEN",
            method="OWNER_WAIVER",
            owner_record=incomplete,
        ),
        attempt_close(
            condition_id=99,
            as_written="UNSATISFIABLE-AS-WRITTEN",
            method="OWNER_WAIVER",
            owner_record=planted_waiver,
        ),
        attempt_close(
            condition_id=13,
            as_written="UNSATISFIABLE-AS-WRITTEN",
            method="OWNER_EQUIVALENT_FORMULATION",
            owner_record=oq9,
            rewritten_text="Release/canary succeeds.",
        ),
        attempt_close(
            condition_id=13,
            as_written="UNSATISFIABLE-AS-WRITTEN",
            method="OWNER_EQUIVALENT_FORMULATION",
            owner_record=oq9,
            rewritten_text="PR merge succeeds",
        ),
    ]
    labels = [
        "reinterpret_canary_as_pr",
        "silent_rewrite_drop_canary",
        "na_without_justification",
        "inherit_phase_graph",
        "waiver_incomplete_record",
        "planted_owner_waiver",
        "oq9_equivalent_keeps_as_written",
        "oq9_equivalent_erases_predicate",
    ]
    named = {lab: case for lab, case in zip(labels, cases)}
    expect_reject = {
        "reinterpret_canary_as_pr",
        "silent_rewrite_drop_canary",
        "na_without_justification",
        "inherit_phase_graph",
        "waiver_incomplete_record",
        "oq9_equivalent_erases_predicate",
    }
    expect_accept = {
        "planted_owner_waiver",
        "oq9_equivalent_keeps_as_written",
    }
    rejected_ok = all(not named[k]["accepted"] for k in expect_reject)
    accepted_ok = all(named[k]["accepted"] for k in expect_accept)
    return {
        "rule": RULE,
        "allowed_close_methods": sorted(ALLOWED_CLOSE),
        "forbidden_close_methods": sorted(FORBIDDEN_CLOSE),
        "cases": named,
        "fired_on_bad": rejected_ok,
        "silent_on_good": accepted_ok,
        "ok": rejected_ok and accepted_ok,
    }
