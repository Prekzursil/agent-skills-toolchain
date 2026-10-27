#!/usr/bin/env python3
"""Council outcome → sequenced action plan (IMP-0340)."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

KIND_TO_TYPE = {
    "commitment": "implement",
    "constraint": "enforce",
    "experiment": "experiment",
    "mitigation": "mitigate",
    "finding": None,
}


class PlanError(ValueError):
    pass


def agreed_id_set(decision: dict[str, Any]) -> set[str]:
    return {
        str(el.get("element_id"))
        for el in (decision.get("agreed_elements") or [])
        if el.get("element_id")
    }


def dissent_id_set(decision: dict[str, Any]) -> set[str]:
    return {
        str(el.get("element_id"))
        for el in (decision.get("dissents") or [])
        if el.get("element_id")
    }


def _topo(elements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {str(el["element_id"]): el for el in elements}
    deps: dict[str, set[str]] = {}
    for el in elements:
        eid = str(el["element_id"])
        pre = el.get("precondition") or {}
        need = set()
        if str(pre.get("type") or "") == "depends_on":
            need = {str(x) for x in (pre.get("element_ids") or [])}
        deps[eid] = need
    remaining = set(by_id)
    ordered: list[dict[str, Any]] = []
    while remaining:
        ready = [eid for eid in remaining if deps[eid].isdisjoint(remaining)]
        if not ready:
            raise PlanError("cyclic depends_on")
        ready.sort(key=lambda e: (int(by_id[e].get("sequence") or 0), e))
        pick = ready[0]
        remaining.remove(pick)
        ordered.append(by_id[pick])
    return ordered


def plan_from_decision(decision: dict[str, Any]) -> dict[str, Any]:
    kind = str(decision.get("outcome_kind") or "DECISION").upper()
    if kind in {"NO-DECISION", "NONE"}:
        return {"actions": [], "omitted": [{"element_id": "*", "reason": "no_decision"}], "outcome_kind": kind}

    elements = list(decision.get("agreed_elements") or [])
    dissent = dissent_id_set(decision)
    conditions = list(decision.get("conditions") or [])
    ordered = _topo(elements)
    actions: list[dict[str, Any]] = []
    omitted: list[dict[str, Any]] = []
    seq = 0
    for el in ordered:
        eid = str(el.get("element_id"))
        owner = str(el.get("owner") or "").strip()
        el_kind = str(el.get("kind") or "")
        atype = KIND_TO_TYPE.get(el_kind)
        if atype is None and el_kind == "finding":
            omitted.append({"element_id": eid, "reason": "finding"})
            continue
        if atype is None:
            atype = el_kind or "implement"
        if not owner:
            omitted.append({"element_id": eid, "reason": "missing_owner"})
            continue
        if eid in dissent:
            omitted.append({"element_id": eid, "reason": "dissent"})
            continue
        seq += 1
        pre = dict(el.get("precondition") or {"type": "always"})
        if kind == "CONDITIONAL" and conditions:
            pre = dict(pre)
            pre["conditions"] = list(conditions)
        actions.append(
            {
                "action_id": f"act-{eid}",
                "traces_to": eid,
                "type": atype,
                "statement": el.get("statement"),
                "owner": owner,
                "sequence": seq,
                "precondition": pre,
                "verification": dict(el.get("verification") or {}),
            }
        )
    return {
        "decision_id": decision.get("decision_id"),
        "outcome_kind": kind,
        "actions": actions,
        "omitted": omitted,
    }


def validate_action(action: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in ("owner", "precondition", "verification"):
        if field not in action or action.get(field) in (None, "", "   "):
            errors.append(f"missing:{field}")
        elif field == "owner" and not str(action.get("owner") or "").strip():
            errors.append("empty-owner")
    return errors


def validate_plan(plan: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    actions = list(plan.get("actions") or [])
    seqs = [int(a.get("sequence") or 0) for a in actions]
    if seqs != sorted(seqs):
        errors.append("actions not ordered by sequence")
    for i, a in enumerate(actions):
        errors.extend(f"action[{i}]:{e}" for e in validate_action(a))
    return errors


def traceability_check(plan: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
    agreed = agreed_id_set(decision)
    dissent_only = dissent_id_set(decision) - agreed
    by_el = {str(el.get("element_id")): el for el in (decision.get("agreed_elements") or [])}
    untraceable: list[dict[str, Any]] = []
    actions = list(plan.get("actions") or [])
    for a in actions:
        aid = str(a.get("action_id") or "")
        traces = str(a.get("traces_to") or "")
        if traces in dissent_only:
            untraceable.append({"action_id": aid, "reason": "traces_to_dissent"})
            continue
        if traces not in agreed:
            untraceable.append({"action_id": aid, "reason": "not_in_agreed_set"})
            continue
        src = by_el.get(traces) or {}
        if str(a.get("statement") or "") != str(src.get("statement") or ""):
            untraceable.append({"action_id": aid, "reason": "statement_mismatch"})
    return {
        "fired": bool(untraceable),
        "untraceable": untraceable,
        "traceable_count": len(actions) - len(untraceable),
        "action_count": len(actions),
    }


def inject_unagreed_action(plan: dict[str, Any]) -> dict[str, Any]:
    clone = json.loads(json.dumps(plan))
    clone.setdefault("actions", []).append(
        {
            "action_id": "act-injected-unagreed",
            "traces_to": "el-not-agreed",
            "type": "implement",
            "statement": "injected unagreed work",
            "owner": "intruder",
            "sequence": 99,
            "precondition": {"type": "always"},
            "verification": {"oracle": "none", "spec": "n/a"},
        }
    )
    return clone


def inject_statement_mismatch(plan: dict[str, Any]) -> dict[str, Any]:
    clone = json.loads(json.dumps(plan))
    if clone.get("actions"):
        clone["actions"][0]["statement"] = "MISMATCHED STATEMENT"
    return clone


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("usage: action_plan.py plan|validate|check ...", file=sys.stderr)
        return 2
    cmd = args[0]
    if cmd == "plan":
        decision = json.loads(Path(args[1]).read_text(encoding="utf-8"))
        plan = plan_from_decision(decision)
        print(json.dumps(plan, indent=2, sort_keys=True))
        return 0
    if cmd == "validate":
        plan = json.loads(Path(args[1]).read_text(encoding="utf-8"))
        errs = validate_plan(plan)
        print(json.dumps({"ok": not errs, "errors": errs}, indent=2, sort_keys=True))
        return 0 if not errs else 1
    if cmd == "check":
        plan = json.loads(Path(args[1]).read_text(encoding="utf-8"))
        decision = json.loads(Path(args[2]).read_text(encoding="utf-8"))
        report = traceability_check(plan, decision)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 1 if report["fired"] else 0
    print(f"unknown command {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
