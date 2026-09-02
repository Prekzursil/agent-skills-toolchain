#!/usr/bin/env python3
"""Evaluate CNL-0081's stopping expression against a council round state.

The expression is quoted verbatim from the catalog title / spec 10940:

    quality_gate == PASS AND unresolved_load_bearing_counterexample == 0

`unresolved_load_bearing_counterexample` is a DERIVED count. A claimed integer
on the state document is ignored. Dual-seat records (same participant both
declares load-bearing and certifies resolution) stay in the unresolved count,
so the conjunction stays SILENT.

Cadence pin (CNL-0076 not delivered on this tree): evaluate at end-of-round,
side-effect free, using the bound environment from bind().
"""
from __future__ import annotations

from typing import Any

from a10_grammar import THIS_EXPRESSION, eval_source

ROLE_REGISTRAR = "LoadBearingRegistrar"
ROLE_CERTIFIER = "ResolutionCertifier"
ROLE_QG = "QualityGateOperator"

EXPRESSION = THIS_EXPRESSION


def has_role(roster: dict[str, Any], pid: str | None, role: str) -> bool:
    if not pid:
        return False
    for p in roster.get("participants") or []:
        if p.get("id") == pid and role in (p.get("roles") or []):
            return True
    return False


def seats_ok(rec: dict[str, Any], roster: dict[str, Any]) -> bool:
    """Seat-incompatibility constraint (CNL-0029 pair, executable here).

    Author cannot declare the record load-bearing.
    Registrar cannot later certify resolution of the same record.
    Certifier cannot be the evidence producer who submitted the resolving bytes.
    Missing seats fail closed (record stays unresolved).
    """
    if not rec.get("declared_load_bearing"):
        return True
    author = rec.get("author_id")
    registrar = rec.get("declared_load_bearing_by")
    if not registrar or registrar == author:
        return False
    if not has_role(roster, registrar, ROLE_REGISTRAR):
        return False
    if not rec.get("resolved"):
        return True
    cert = rec.get("resolved_by")
    evidence = rec.get("evidence_producer_id")
    if not cert:
        return False
    if cert in {author, registrar, evidence}:
        return False
    if not has_role(roster, cert, ROLE_CERTIFIER):
        return False
    return True


def derived_unresolved(records: list[dict[str, Any]], roster: dict[str, Any]) -> int:
    n = 0
    for rec in records:
        if not rec.get("declared_load_bearing"):
            continue
        if rec.get("resolved") and seats_ok(rec, roster):
            continue
        n += 1
    return n


def effective_quality_gate(state: dict[str, Any]) -> str:
    claimed = state.get("quality_gate")
    roster = state.get("roster") or {}
    op = state.get("quality_gate_operator_id")
    if claimed != "PASS":
        return "FAIL"
    if not has_role(roster, op, ROLE_QG):
        return "FAIL"
    for rec in state.get("counterexamples") or []:
        if rec.get("declared_load_bearing") and rec.get("declared_load_bearing_by") == op:
            return "FAIL"
    return "PASS"


def bind(state: dict[str, Any]) -> dict[str, Any]:
    roster = state.get("roster") or {}
    records = list(state.get("counterexamples") or [])
    derived = derived_unresolved(records, roster)
    claimed = state.get("unresolved_load_bearing_counterexample")
    qg = effective_quality_gate(state)
    return {
        "quality_gate": qg,
        "unresolved_load_bearing_counterexample": derived,
        "claimed_unresolved": claimed,
        "claimed_mismatch": claimed is not None and claimed != derived,
        "expression": EXPRESSION,
    }


def decide(state: dict[str, Any]) -> dict[str, Any]:
    env = bind(state)
    fired = eval_source(EXPRESSION, env)
    return {
        "decision": "FIRE" if fired else "SILENT",
        "fired": fired,
        "env": env,
        "expression": EXPRESSION,
    }
