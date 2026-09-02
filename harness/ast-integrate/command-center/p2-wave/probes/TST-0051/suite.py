"""Conformance suite: identity, no-skip, PR-ONLY, evidence, waiver.

Both-states: a conforming snapshot passes every rule; each rule has a
deliberate mutant that fails that rule. Live mismatch is a FINDING, not a
suite defect.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from contract import FORBIDDEN_UNDER_PR_ONLY, RULES, empty_record

CONFORMING_GATES = (
    "ci-green-pr-head",
    "lifecycle-install-runtime",
    "lifecycle-upgrade",
    "lifecycle-rollback",
)


def _base_records(ids: list[str], *, status: str = "PASS", evidence: str = "fixture-receipt") -> dict[str, Any]:
    out: dict[str, Any] = {}
    for gid in ids:
        rec = empty_record(gid)
        rec["status"] = status
        rec["evidence"] = evidence
        rec["required"] = True
        out[gid] = rec
    return out


def conforming_snapshot() -> dict[str, Any]:
    ids = list(CONFORMING_GATES)
    return {
        "policy_declared": list(ids),
        "tooling_enforced": list(ids),
        "ran": list(ids),
        "allow_release": True,
        "release_mode": "PR-ONLY",
        "records": _base_records(ids),
    }


def mutant_for(rule_id: str) -> dict[str, Any]:
    snap = deepcopy(conforming_snapshot())
    if rule_id == "R-identity":
        extra = "semver-bump-linter"
        snap["policy_declared"] = list(snap["policy_declared"]) + [extra]
        snap["records"][extra] = empty_record(extra)
        snap["records"][extra]["status"] = "NEVER-RUN"
        return snap
    if rule_id == "R-no-skip":
        skipped = snap["policy_declared"][-1]
        snap["ran"] = [g for g in snap["ran"] if g != skipped]
        snap["allow_release"] = True
        snap["records"][skipped]["status"] = "NEVER-RUN"
        snap["records"][skipped]["evidence"] = ""
        return snap
    if rule_id == "R-pr-only":
        bad = "marketplace-publish"
        snap["policy_declared"] = list(snap["policy_declared"]) + [bad]
        snap["tooling_enforced"] = list(snap["tooling_enforced"]) + [bad]
        snap["ran"] = list(snap["ran"]) + [bad]
        rec = empty_record(bad)
        rec["status"] = "PASS"
        rec["evidence"] = "published-to-index"
        rec["required"] = True
        snap["records"][bad] = rec
        return snap
    if rule_id == "R-evidence":
        gid = snap["policy_declared"][0]
        snap["records"][gid]["status"] = "PASS"
        snap["records"][gid]["evidence"] = ""
        return snap
    if rule_id == "R-waiver":
        gid = "sc13-canary-succeeds"
        snap["policy_declared"] = list(snap["policy_declared"]) + [gid]
        snap["tooling_enforced"] = list(snap["tooling_enforced"]) + [gid]
        snap["ran"] = list(snap["ran"]) + [gid]
        rec = empty_record(gid)
        rec["status"] = "PASS"
        rec["evidence"] = "reinterpreted-as-pr-merge"
        rec["unsatisfiable"] = True
        rec["waiver_id"] = ""
        rec["required"] = True
        snap["records"][gid] = rec
        return snap
    raise KeyError(rule_id)


def evaluate(snapshot: dict[str, Any]) -> dict[str, Any]:
    pol = list(snapshot.get("policy_declared") or [])
    tool = list(snapshot.get("tooling_enforced") or [])
    ran = set(snapshot.get("ran") or [])
    allow = bool(snapshot.get("allow_release"))
    records: dict[str, Any] = dict(snapshot.get("records") or {})
    results: list[dict[str, Any]] = []

    pol_s, tool_s = set(pol), set(tool)
    identity_ok = pol_s == tool_s
    results.append(
        {
            "id": "R-identity",
            "pass": identity_ok,
            "detail": (
                "sets equal"
                if identity_ok
                else (
                    f"policy-minus-tooling={sorted(pol_s - tool_s)} "
                    f"tooling-minus-policy={sorted(tool_s - pol_s)}"
                )
            ),
        }
    )

    unrun = [g for g in pol if g not in ran]
    skip_ok = not (allow and unrun)
    results.append(
        {
            "id": "R-no-skip",
            "pass": skip_ok,
            "detail": (
                "no unrun declared gate while release allowed"
                if skip_ok
                else f"allow_release with never-run={unrun}"
            ),
        }
    )

    forbidden_hit = [
        g
        for g in pol
        if g in FORBIDDEN_UNDER_PR_ONLY
        and str((records.get(g) or {}).get("status") or "").upper()
        in {"PASS", "RUN", "TOOLING-PRESENT"}
        and (records.get(g) or {}).get("required", True)
    ]
    pr_ok = not forbidden_hit
    results.append(
        {
            "id": "R-pr-only",
            "pass": pr_ok,
            "detail": "no forbidden PR-ONLY gate required+run" if pr_ok else f"forbidden={forbidden_hit}",
        }
    )

    evidence_bad = []
    for gid, rec in records.items():
        st = str((rec or {}).get("status") or "").upper()
        ev = str((rec or {}).get("evidence") or "").strip()
        if st == "PASS" and not ev:
            evidence_bad.append(gid)
    ev_ok = not evidence_bad
    results.append(
        {
            "id": "R-evidence",
            "pass": ev_ok,
            "detail": "no PASS without evidence" if ev_ok else f"pass-without-evidence={evidence_bad}",
        }
    )

    waiver_bad = []
    for gid, rec in records.items():
        rec = rec or {}
        if rec.get("unsatisfiable") and not str(rec.get("waiver_id") or "").strip():
            st = str(rec.get("status") or "").upper()
            if st in {"PASS", "CLOSED", "WAIVED"}:
                waiver_bad.append(gid)
    waiver_ok = not waiver_bad
    results.append(
        {
            "id": "R-waiver",
            "pass": waiver_ok,
            "detail": "unsatisfiable closures carry a waiver id" if waiver_ok else f"no-waiver={waiver_bad}",
        }
    )

    by_id = {r["id"]: r for r in results}
    all_pass = all(r["pass"] for r in results)
    return {
        "results": results,
        "by_id": by_id,
        "all_pass": all_pass,
        "rule_count": len(results),
        "expected_rules": [r["id"] for r in RULES],
    }


def both_states() -> dict[str, Any]:
    good = evaluate(conforming_snapshot())
    mutants: dict[str, Any] = {}
    per_rule_negative = True
    for rule in RULES:
        rid = rule["id"]
        ev = evaluate(mutant_for(rid))
        fired = (not ev["by_id"][rid]["pass"]) and good["by_id"][rid]["pass"]
        mutants[rid] = {
            "mutant_pass": ev["all_pass"],
            "rule_pass": ev["by_id"][rid]["pass"],
            "fired_on_mutant": fired,
            "detail": ev["by_id"][rid]["detail"],
            "negative_case": rule["negative"],
        }
        if not fired:
            per_rule_negative = False
    return {
        "conforming_all_pass": good["all_pass"],
        "conforming": good,
        "mutants": mutants,
        "negative_case_per_rule": per_rule_negative,
        "both_states_holds": bool(good["all_pass"] and per_rule_negative),
        "rule_ids": [r["id"] for r in RULES],
    }
