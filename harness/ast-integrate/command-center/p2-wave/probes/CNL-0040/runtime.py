"""Executable admissibility runtime for the 6 JUDICIAL protocols (CNL-0040)."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS_PATH = HERE / "fixtures" / "runs.json"

RELIABLE_KINDS = frozenset({"record", "measurement", "sworn-statement"})

# Designed semantics. record_id is the catalogue P-id the verdict must cite.
PROTOCOLS = {
    "P14": {
        "record_id": "P14",
        "slug": "judge-and-jury",
        "family": "JUDICIAL",
        "admissibility_standard_id": "RELEVANCE_AND_RELIABILITY",
        "admissibility_officer_role": "judge",
        "decider_role": "jury",
        "executable": True,
        "missing_element": None,
        "stopping": {
            "kind": "expression",
            "expr": {
                "op": "AND",
                "args": [
                    {"op": "ALL", "var": "jury_ballots_cast"},
                    {"op": "NOT", "args": [{"op": "ANY", "var": "pending_objections"}]},
                ],
            },
        },
        "turn_schedule": [
            {"id": "open-docket", "actor": "clerk", "action": "publish_charged_claims"},
            {"id": "offer", "actor": "advocate", "action": "offer_exhibits"},
            {"id": "object", "actor": "opponent", "action": "optional_object"},
            {"id": "rule", "actor": "judge", "action": "rule_admissibility"},
            {"id": "seal", "actor": "clerk", "action": "publish_admitted_only"},
            {"id": "ballot", "actor": "jury", "action": "cast_ballots_on_admitted"},
            {"id": "tally", "actor": "clerk", "action": "tally_excluding_judge"},
        ],
    },
    "P15": {
        "record_id": "P15",
        "slug": "claim-by-claim-adjudication",
        "family": "JUDICIAL",
        "admissibility_standard_id": "ATOMIC_CITABLE_CLAIM",
        "admissibility_officer_role": "claims-clerk",
        "decider_role": "panel",
        "executable": True,
        "missing_element": None,
        "stopping": {
            "kind": "expression",
            "expr": {
                "op": "ALL",
                "var": "admitted_claims_balloted_or_unresolved",
            },
        },
        "turn_schedule": [
            {"id": "docket-claims", "actor": "clerk", "action": "list_atomic_claims"},
            {"id": "gate", "actor": "claims-clerk", "action": "admit_or_exclude_per_claim"},
            {"id": "adjudicate", "actor": "panel", "action": "vote_admitted_claims_only"},
        ],
    },
    "P16": {
        "record_id": "P16",
        "slug": "grand-jury-threshold",
        "family": "JUDICIAL",
        "admissibility_standard_id": "PROBABLE_CAUSE_PACKET",
        "admissibility_officer_role": "threshold-clerk",
        "decider_role": "grand-jury",
        "executable": True,
        "missing_element": None,
        "stopping": {
            "kind": "expression",
            "expr": {"op": "ALL", "var": "grand_jury_ballots_cast"},
        },
        "turn_schedule": [
            {"id": "present", "actor": "presenter", "action": "offer_threshold_exhibits"},
            {"id": "pack", "actor": "threshold-clerk", "action": "seal_probable_cause_packet"},
            {"id": "bill", "actor": "grand-jury", "action": "true_bill_or_no_bill"},
        ],
    },
    "P17": {
        "record_id": "P17",
        "slug": "jury-with-allowed-hung",
        "family": "JUDICIAL",
        "admissibility_standard_id": "RELEVANCE_AND_RELIABILITY",
        "admissibility_officer_role": "judge",
        "decider_role": "jury",
        "executable": True,
        "missing_element": None,
        "hung_is_terminal": True,
        "stopping": {
            "kind": "expression",
            "expr": {
                "op": "AND",
                "args": [
                    {"op": "ALL", "var": "jury_ballots_cast"},
                    {
                        "op": "OR",
                        "args": [
                            {"op": "UNANIMOUS", "var": "jury_votes"},
                            {"op": "AND", "args": [{"var": "rounds_exhausted"}]},
                        ],
                    },
                ],
            },
        },
        "turn_schedule": [
            {"id": "open-docket", "actor": "clerk", "action": "publish_charged_claims"},
            {"id": "rule", "actor": "judge", "action": "rule_admissibility"},
            {"id": "ballot", "actor": "jury", "action": "cast_ballots_on_admitted"},
            {"id": "hung-or-verdict", "actor": "clerk", "action": "record_hung_if_not_unanimous"},
        ],
    },
    "P18": {
        "record_id": "P18",
        "slug": "two-key-dual-control",
        "family": "JUDICIAL",
        "admissibility_standard_id": "DUAL_CONCURRENCE",
        "admissibility_officer_role": "officer-pair",
        "decider_role": "dual-key-deciders",
        "executable": True,
        "missing_element": None,
        "dual_officers_required": True,
        "stopping": {
            "kind": "expression",
            "expr": {
                "op": "AND",
                "args": [
                    {"op": "ALL", "var": "dual_key_ballots_cast"},
                    {"op": "ALL", "var": "exhibits_have_two_officer_rulings"},
                ],
            },
        },
        "turn_schedule": [
            {"id": "offer", "actor": "requestor", "action": "offer_exhibits"},
            {"id": "key-a", "actor": "officer-a", "action": "independent_admit_or_exclude"},
            {"id": "key-b", "actor": "officer-b", "action": "independent_admit_or_exclude"},
            {"id": "concur", "actor": "runtime", "action": "admit_iff_both_admit"},
            {"id": "authorize", "actor": "dual-deciders", "action": "two_key_verdict"},
        ],
    },
    "P19": {
        "record_id": "P19",
        "slug": "rfc-last-call",
        "family": "JUDICIAL",
        "admissibility_standard_id": "IN_WINDOW_SPECIFIC_CITATION",
        "admissibility_officer_role": "last-call-chair",
        "decider_role": "participants",
        "executable": True,
        "missing_element": None,
        "stopping": {
            "kind": "expression",
            "expr": {
                "op": "AND",
                "args": [
                    {"var": "window_closed"},
                    {"op": "ALL", "var": "in_scope_objections_addressed_or_recorded"},
                ],
            },
        },
        "turn_schedule": [
            {"id": "open-window", "actor": "editor", "action": "publish_last_call_window"},
            {"id": "object", "actor": "participants", "action": "file_objections"},
            {"id": "scope", "actor": "chair", "action": "rule_objection_in_or_out_of_scope"},
            {"id": "close", "actor": "editor", "action": "close_window"},
            {"id": "consensus", "actor": "participants", "action": "count_consensus_without_chair_vote"},
        ],
    },
}


def load_runs() -> dict:
    return json.loads(RUNS_PATH.read_text(encoding="utf-8"))


def _reasons_relevance_reliability(ex: dict, charged: set[str]) -> list[str]:
    reasons: list[str] = []
    if ex.get("claim_id") not in charged:
        reasons.append("not-relevant")
    if ex.get("source_kind") not in RELIABLE_KINDS:
        reasons.append("not-reliable-kind")
    if not ex.get("provenance_hash"):
        reasons.append("no-provenance")
    return reasons


def _reasons_atomic_citable(ex: dict, charged: set[str]) -> list[str]:
    reasons: list[str] = []
    if ex.get("claim_id") not in charged:
        reasons.append("not-on-docket")
    if ex.get("atomic") is False:
        reasons.append("not-atomic")
    if not ex.get("cites_record_id"):
        reasons.append("no-record-citation")
    if ex.get("source_kind") == "argument":
        reasons.append("argument-not-claim")
    return reasons


def _reasons_probable_cause(ex: dict, charged: set[str]) -> list[str]:
    reasons: list[str] = []
    if ex.get("claim_id") not in charged:
        reasons.append("not-relevant")
    if ex.get("source_kind") not in RELIABLE_KINDS:
        reasons.append("not-threshold-kind")
    if ex.get("source_kind") == "argument" or ex.get("threshold_only") is False:
        if ex.get("source_kind") == "argument" or ex.get("threshold_only") is False:
            reasons.append("full-proof-or-argument")
    if not ex.get("provenance_hash"):
        reasons.append("no-provenance")
    # Dedup while preserving order
    out: list[str] = []
    for r in reasons:
        if r not in out:
            out.append(r)
    return out


def _reasons_last_call(ex: dict, window: dict | None) -> list[str]:
    reasons: list[str] = []
    win = window or {}
    ts = ex.get("timestamp")
    start, end = win.get("start"), win.get("end")
    if ts is None or start is None or end is None or not (start <= ts <= end):
        reasons.append("out-of-window")
    if not ex.get("section_id"):
        reasons.append("no-section-citation")
    if not ex.get("claim_id"):
        reasons.append("nonspecific")
    return reasons


def standard_reasons(protocol_id: str, ex: dict, run: dict) -> list[str]:
    charged = set(run.get("charged_claims") or [])
    if protocol_id in {"P14", "P17", "P18"}:
        return _reasons_relevance_reliability(ex, charged)
    if protocol_id == "P15":
        return _reasons_atomic_citable(ex, charged)
    if protocol_id == "P16":
        return _reasons_probable_cause(ex, charged)
    if protocol_id == "P19":
        return _reasons_last_call(ex, run.get("window"))
    return ["unknown-protocol"]


def execute(run: dict) -> dict:
    pid = str(run.get("protocol_id") or "")
    spec = PROTOCOLS.get(pid)
    if spec is None:
        return {
            "ok": False,
            "fires": True,
            "protocol_id": pid,
            "violations": [{"code": "UNKNOWN_PROTOCOL", "detail": pid}],
            "admitted": [],
            "excluded": [],
            "trace": [],
        }
    officers = [str(x) for x in (run.get("officers") or [])]
    deciders = [str(x) for x in (run.get("deciders") or [])]
    officer_set = set(officers)
    decider_set = set(deciders)
    violations: list[dict] = []
    trace: list[dict] = []

    if officer_set & decider_set:
        violations.append(
            {
                "code": "GATEKEEPER_IS_DECIDER",
                "detail": sorted(officer_set & decider_set),
            }
        )

    exhibits = {str(e["id"]): e for e in (run.get("exhibits") or [])}
    rulings = list(run.get("rulings") or [])
    by_ex: dict[str, list[dict]] = {}
    for r in rulings:
        by_ex.setdefault(str(r.get("exhibit_id")), []).append(r)

    admitted: list[str] = []
    excluded: list[str] = []

    for step in spec["turn_schedule"]:
        trace.append({"step": step["id"], "actor": step["actor"], "action": step["action"]})

    dual = bool(spec.get("dual_officers_required"))
    for eid, ex in exhibits.items():
        reasons = standard_reasons(pid, ex, run)
        passes = not reasons
        erulings = by_ex.get(eid, [])
        admit_officers = [
            str(r.get("officer_id"))
            for r in erulings
            if r.get("decision") == "admit" and str(r.get("officer_id")) in officer_set
        ]
        exclude_officers = [
            str(r.get("officer_id"))
            for r in erulings
            if r.get("decision") == "exclude" and str(r.get("officer_id")) in officer_set
        ]
        if dual:
            unique_admit = sorted(set(admit_officers))
            if passes and len(unique_admit) >= 2:
                admitted.append(eid)
            else:
                excluded.append(eid)
                if eid not in excluded[:]:
                    pass
                if passes and 0 < len(unique_admit) < 2:
                    violations.append(
                        {
                            "code": "SINGLE_KEY_ADMIT",
                            "detail": {"exhibit_id": eid, "admit_officers": unique_admit},
                        }
                    )
        else:
            officer_says_admit = any(r.get("decision") == "admit" for r in erulings)
            if officer_says_admit and not passes:
                violations.append(
                    {
                        "code": "STANDARD_VIOLATED",
                        "detail": {"exhibit_id": eid, "reasons": reasons},
                    }
                )
                excluded.append(eid)
            elif officer_says_admit and passes:
                admitted.append(eid)
            else:
                excluded.append(eid)
                if passes and not erulings:
                    violations.append(
                        {
                            "code": "UNRULED_EXHIBIT",
                            "detail": eid,
                        }
                    )
        trace.append(
            {
                "exhibit_id": eid,
                "standard_passes": passes,
                "reasons": reasons,
                "admit_officers": admit_officers,
                "exclude_officers": exclude_officers,
            }
        )

    admitted_set = set(admitted)
    excluded_set = set(excluded)
    ballots = list(run.get("ballots") or [])
    for b in ballots:
        agent = str(b.get("agent_id") or "")
        ev = [str(x) for x in (b.get("evidence_ids") or [])]
        if agent in officer_set:
            violations.append(
                {
                    "code": "OFFICER_CAST_VERDICT",
                    "detail": agent,
                }
            )
        leaked = [e for e in ev if e in excluded_set]
        if leaked:
            violations.append(
                {
                    "code": "DECIDER_SAW_EXCLUDED",
                    "detail": {"agent": agent, "excluded": leaked},
                }
            )
        unknown = [e for e in ev if e not in admitted_set and e not in excluded_set]
        if unknown:
            violations.append(
                {
                    "code": "BALLOT_UNKNOWN_EVIDENCE",
                    "detail": {"agent": agent, "ids": unknown},
                }
            )

    if spec.get("hung_is_terminal") and run.get("rounds_exhausted"):
        decider_votes = [
            b.get("vote") for b in ballots if str(b.get("agent_id")) in decider_set
        ]
        unanimous = len(set(decider_votes)) == 1 and len(decider_votes) == len(decider_set)
        if not unanimous:
            officer_voted = any(str(b.get("agent_id")) in officer_set for b in ballots)
            if str(run.get("verdict") or "") != "HUNG" or officer_voted:
                violations.append(
                    {
                        "code": "HUNG_BROKEN_BY_OFFICER",
                        "detail": {
                            "verdict": run.get("verdict"),
                            "officer_voted": officer_voted,
                            "votes": decider_votes,
                        },
                    }
                )

    if pid == "P19" and run.get("chair_declared_consensus") is True:
        violations.append(
            {
                "code": "CHAIR_DECLARED_CONSENSUS",
                "detail": "last-call-chair issued consensus_call",
            }
        )

    # Dedup violation codes+detail for stable output
    seen = set()
    uniq: list[dict] = []
    for v in violations:
        key = json.dumps(v, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(v)

    fires = len(uniq) > 0
    return {
        "ok": not fires,
        "fires": fires,
        "protocol_id": pid,
        "record_id": spec["record_id"],
        "standard": spec["admissibility_standard_id"],
        "officer_role": spec["admissibility_officer_role"],
        "decider_role": spec["decider_role"],
        "violations": uniq,
        "admitted": admitted,
        "excluded": excluded,
        "verdict": run.get("verdict"),
        "trace": trace,
        "executable": True,
    }


def execute_named(kind: str, name: str) -> dict:
    runs = load_runs()
    bucket = runs.get(kind) or {}
    if name not in bucket:
        raise KeyError(f"{kind}/{name}")
    result = execute(bucket[name])
    result["fixture_id"] = bucket[name].get("id") or name
    result["planted_defect"] = bucket[name].get("planted_defect")
    return result


def execute_all_good() -> dict[str, dict]:
    runs = load_runs()
    out = {}
    for name, run in (runs.get("good") or {}).items():
        out[name] = execute(run)
        out[name]["fixture_id"] = run.get("id") or name
    return out
