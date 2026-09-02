"""Executable runtime semantics for the 7 TRADECRAFT protocol records.

Schedules are designed semantics for catalog-named SAT techniques. They are
not extracted from 12-COUNCIL-PROTOCOLS-AND-PRESETS.json (absent on this tree).
"""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES = HERE / "fixtures" / "known_good_cases.json"

CELLS = {"C", "I", "N", "NA"}
QOI_CLASS = {"high", "medium", "low", "reject"}

# Explicit operator aliases: only these names can collide across families.
OPERATOR_ALIASES = {
    "premortem": "prospective-hindsight-failure-enumeration",
    "kill-the-company": "prospective-hindsight-failure-enumeration",
}
TIME_ALIASES = {
    "premortem": "before-decision",
    "kill-the-company": "before-decision",
}
SHAPE_ALIASES = {
    "premortem": "failure-mode-list",
    "kill-the-company": "failure-mode-list",
}

TRADECRAFT_MECHANISMS = {
    "P38": {
        "time_orientation": "before-decision",
        "core_operator": "diagnosticity-matrix",
        "artifact_shape": "matrix",
        "artifact_name": "hypothesis_matrix",
        "artifact_schema_keys": [
            "hypotheses",
            "evidence",
            "cells",
            "diagnosticity",
            "ranking",
        ],
        "turns": [
            "collect_hypotheses",
            "collect_evidence",
            "fill_matrix",
            "score_diagnosticity",
            "rank_hypotheses",
        ],
        "stopping": "matrix complete AND ranking non-empty AND len(hypotheses)>=2",
    },
    "P39": {
        "time_orientation": "atemporal",
        "core_operator": "assumption-inversion",
        "artifact_shape": "register",
        "artifact_name": "assumption_register",
        "artifact_schema_keys": [
            "claims",
            "assumptions",
            "survivors",
        ],
        "turns": [
            "collect_claims",
            "extract_assumptions",
            "tag_load_bearing",
            "invert_load_bearing",
            "emit_survivors",
        ],
        "stopping": "every load-bearing assumption has if_false_consequence and status",
    },
    "P40": {
        "time_orientation": "atemporal",
        "core_operator": "source-scoring",
        "artifact_shape": "ledger",
        "artifact_name": "source_quality_ledger",
        "artifact_schema_keys": [
            "sources",
            "classifications",
        ],
        "turns": [
            "list_sources",
            "score_credibility",
            "score_completeness",
            "count_corroboration",
            "classify",
        ],
        "stopping": "every source has credibility, completeness, corroboration, classification",
    },
    "P41": {
        "time_orientation": "atemporal",
        "core_operator": "deception-indicator-scoring",
        "artifact_shape": "indicator-list",
        "artifact_name": "deception_indicators",
        "artifact_schema_keys": [
            "denied_intent",
            "indicators",
            "deception_likelihood",
            "verdict",
        ],
        "turns": [
            "state_denied_intent_hypothesis",
            "list_indicators",
            "observe_each",
            "score",
            "emit_verdict",
        ],
        "stopping": "every indicator observed AND verdict present",
    },
    "P42": {
        "time_orientation": "atemporal",
        "core_operator": "argument-graph",
        "artifact_shape": "graph",
        "artifact_name": "argument_graph",
        "artifact_schema_keys": [
            "nodes",
            "edges",
            "ungrounded_claims",
        ],
        "turns": [
            "extract_claims",
            "attach_reasons",
            "attach_objections",
            "attach_evidence",
            "emit_ungrounded",
        ],
        "stopping": "every claim node is supported or listed in ungrounded_claims",
    },
    "P43": {
        "time_orientation": "before-decision",
        "core_operator": "prospective-hindsight-failure-enumeration",
        "artifact_shape": "failure-mode-list",
        "artifact_name": "premortem_failure_modes",
        "artifact_schema_keys": [
            "frozen_plan",
            "assumed_failed",
            "failure_modes",
        ],
        "turns": [
            "freeze_plan",
            "assume_failure",
            "enumerate_causes",
            "early_warnings",
            "preemptive_controls",
        ],
        "stopping": "plan frozen AND assumed_failed AND every mode has warning and control",
    },
    "P44": {
        "time_orientation": "after-failure",
        "core_operator": "retrospective-why-chain",
        "artifact_shape": "causal-chain",
        "artifact_name": "causal_chain",
        "artifact_schema_keys": [
            "observed_failure",
            "why_steps",
            "root_cause",
            "corrective_action",
        ],
        "turns": [
            "state_observed_failure",
            "why_1",
            "why_2",
            "why_3",
            "why_4",
            "why_5",
            "name_root_cause",
            "name_corrective_action",
        ],
        "stopping": "len(why_steps)==5 AND root_cause AND corrective_action",
    },
}


def norm_name(name: str) -> str:
    return name.split("(")[0].strip().strip("-").lower()


def sibling_mechanism(record: dict, family: str) -> dict:
    slug = norm_name(record["name"])
    return {
        "id": record["id"],
        "name": record["name"],
        "family": family,
        "time_orientation": TIME_ALIASES.get(slug, "atemporal"),
        "core_operator": OPERATOR_ALIASES.get(slug, f"named:{slug}"),
        "artifact_shape": SHAPE_ALIASES.get(slug, f"named:{slug}"),
    }


def find_duplicates(tradecraft_records: list[dict], other_families: dict) -> list[dict]:
    """Duplicate iff same (time_orientation, core_operator) across families."""
    t_mechs = []
    for rec in tradecraft_records:
        pid = rec["id"]
        mech = TRADECRAFT_MECHANISMS[pid]
        t_mechs.append(
            {
                "id": pid,
                "name": rec["name"],
                "family": "TRADECRAFT",
                "time_orientation": mech["time_orientation"],
                "core_operator": mech["core_operator"],
                "artifact_shape": mech["artifact_shape"],
            }
        )
    others = []
    for fam, recs in (other_families or {}).items():
        for rec in recs:
            others.append(sibling_mechanism(rec, fam))
    out = []
    for t in t_mechs:
        for o in others:
            if (
                t["core_operator"] == o["core_operator"]
                and t["time_orientation"] == o["time_orientation"]
            ):
                out.append(
                    {
                        "tradecraft_id": t["id"],
                        "tradecraft_name": t["name"],
                        "other_id": o["id"],
                        "other_name": o["name"],
                        "other_family": o["family"],
                        "shared_operator": t["core_operator"],
                        "shared_time": t["time_orientation"],
                        "criterion": (
                            "same (time_orientation, core_operator) across families; "
                            "names differ"
                        ),
                    }
                )
    out.sort(key=lambda r: (r["tradecraft_id"], r["other_id"]))
    return out


def _load_cases() -> dict:
    return json.loads(CASES.read_text(encoding="utf-8"))


def run_p38(case: dict) -> dict:
    hyps = list(case.get("hypotheses") or [])
    ev = list(case.get("evidence") or [])
    if len(hyps) < 2:
        raise ValueError("missing-element:hypotheses>=2")
    if not ev:
        raise ValueError("missing-element:evidence")
    cells = {}
    for row in ev:
        eid = row["id"]
        for h in hyps:
            val = (row.get("cells") or {}).get(h)
            if val not in CELLS:
                raise ValueError(f"missing-element:cell[{eid},{h}]")
            cells[f"{eid}|{h}"] = val
    diagnosticity = {}
    for row in ev:
        vals = {cells[f"{row['id']}|{h}"] for h in hyps}
        diagnosticity[row["id"]] = 0 if len(vals) == 1 else 1
    scores = []
    for h in hyps:
        inconsistent = sum(1 for row in ev if cells[f"{row['id']}|{h}"] == "I")
        consistent = sum(1 for row in ev if cells[f"{row['id']}|{h}"] == "C")
        scores.append({"hypothesis": h, "inconsistent": inconsistent, "consistent": consistent})
    ranking = sorted(scores, key=lambda s: (s["inconsistent"], -s["consistent"], s["hypothesis"]))
    return {
        "hypotheses": hyps,
        "evidence": [row["id"] for row in ev],
        "cells": cells,
        "diagnosticity": diagnosticity,
        "ranking": ranking,
    }


def run_p39(case: dict) -> dict:
    claims = list(case.get("claims") or [])
    assumptions = deepcopy(list(case.get("assumptions") or []))
    if not claims:
        raise ValueError("missing-element:claims")
    if not assumptions:
        raise ValueError("missing-element:assumptions")
    for a in assumptions:
        if "load_bearing" not in a:
            raise ValueError(f"missing-element:load_bearing:{a.get('id')}")
        if a["load_bearing"] and not a.get("if_false_consequence"):
            raise ValueError(f"missing-element:if_false_consequence:{a.get('id')}")
        if a.get("status") not in {"holds", "fails", "untested"}:
            raise ValueError(f"missing-element:status:{a.get('id')}")
    survivors = [a for a in assumptions if a["status"] != "fails"]
    return {
        "claims": claims,
        "assumptions": assumptions,
        "survivors": survivors,
    }


def run_p40(case: dict) -> dict:
    sources = deepcopy(list(case.get("sources") or []))
    if not sources:
        raise ValueError("missing-element:sources")
    classifications = {}
    for s in sources:
        sid = s.get("id")
        for key in ("credibility", "completeness", "corroboration"):
            if key not in s:
                raise ValueError(f"missing-element:{key}:{sid}")
        cred, comp, cor = s["credibility"], s["completeness"], s["corroboration"]
        if not (0 <= cred <= 1 and 0 <= comp <= 1 and cor >= 0):
            raise ValueError(f"missing-element:score-range:{sid}")
        if cred < 0.3 or cor < 1:
            klass = "reject" if cred < 0.2 else "low"
        elif cred >= 0.8 and comp >= 0.7 and cor >= 2:
            klass = "high"
        else:
            klass = "medium"
        s["classification"] = klass
        classifications[sid] = klass
        if klass not in QOI_CLASS:
            raise ValueError(f"missing-element:classification:{sid}")
    return {"sources": sources, "classifications": classifications}


def run_p41(case: dict) -> dict:
    denied = case.get("denied_intent")
    indicators = deepcopy(list(case.get("indicators") or []))
    if not denied:
        raise ValueError("missing-element:denied_intent")
    if not indicators:
        raise ValueError("missing-element:indicators")
    scores = []
    for ind in indicators:
        if "observed" not in ind or "expected_if_deception" not in ind:
            raise ValueError(f"missing-element:observation:{ind.get('id')}")
        match = ind["observed"] == ind["expected_if_deception"]
        ind["score"] = 1 if match else 0
        scores.append(ind["score"])
    likelihood = sum(scores) / len(scores)
    verdict = "deception-indicated" if likelihood >= 0.5 else "deception-not-indicated"
    return {
        "denied_intent": denied,
        "indicators": indicators,
        "deception_likelihood": likelihood,
        "verdict": verdict,
    }


def run_p42(case: dict) -> dict:
    nodes = deepcopy(list(case.get("nodes") or []))
    edges = deepcopy(list(case.get("edges") or []))
    if not nodes:
        raise ValueError("missing-element:nodes")
    ids = {n["id"] for n in nodes}
    claims = [n for n in nodes if n.get("kind") == "claim"]
    if not claims:
        raise ValueError("missing-element:claim-nodes")
    for e in edges:
        if e.get("src") not in ids or e.get("dst") not in ids:
            raise ValueError("missing-element:edge-endpoint")
        if e.get("kind") not in {"supports", "attacks", "undercuts"}:
            raise ValueError("missing-element:edge-kind")
    supported = {e["dst"] for e in edges if e["kind"] == "supports"}
    ungrounded = [c["id"] for c in claims if c["id"] not in supported]
    return {
        "nodes": nodes,
        "edges": edges,
        "ungrounded_claims": ungrounded,
    }


def run_p43(case: dict) -> dict:
    plan = case.get("frozen_plan")
    modes = deepcopy(list(case.get("failure_modes") or []))
    if not plan:
        raise ValueError("missing-element:frozen_plan")
    if not modes:
        raise ValueError("missing-element:failure_modes")
    for m in modes:
        if not m.get("early_warning"):
            raise ValueError(f"missing-element:early_warning:{m.get('id')}")
        if not m.get("preemptive_control"):
            raise ValueError(f"missing-element:preemptive_control:{m.get('id')}")
    return {
        "frozen_plan": plan,
        "assumed_failed": True,
        "failure_modes": modes,
    }


def run_p44(case: dict) -> dict:
    observed = case.get("observed_failure")
    steps = list(case.get("why_steps") or [])
    root = case.get("root_cause")
    action = case.get("corrective_action")
    if not observed:
        raise ValueError("missing-element:observed_failure")
    if len(steps) != 5 or any(not s for s in steps):
        raise ValueError("missing-element:why_steps==5")
    if not root:
        raise ValueError("missing-element:root_cause")
    if not action:
        raise ValueError("missing-element:corrective_action")
    return {
        "observed_failure": observed,
        "why_steps": steps,
        "root_cause": root,
        "corrective_action": action,
    }


RUNNERS = {
    "P38": run_p38,
    "P39": run_p39,
    "P40": run_p40,
    "P41": run_p41,
    "P42": run_p42,
    "P43": run_p43,
    "P44": run_p44,
}


def validate_artifact(pid: str, artifact: dict) -> list[str]:
    spec = TRADECRAFT_MECHANISMS[pid]
    missing = [k for k in spec["artifact_schema_keys"] if k not in artifact]
    return [f"missing-element:artifact.{k}" for k in missing]


def run_protocol(pid: str, case: dict | None = None) -> dict:
    spec = TRADECRAFT_MECHANISMS[pid]
    cases = case if case is not None else _load_cases()[pid]
    try:
        artifact = RUNNERS[pid](cases)
    except (KeyError, TypeError, ValueError) as exc:
        return {
            "record_id": pid,
            "executability": "NOT-EXECUTABLE",
            "missing_element": str(exc),
            "artifact": None,
            "turns": spec["turns"],
            "stopping": spec["stopping"],
        }
    errors = validate_artifact(pid, artifact)
    if errors:
        return {
            "record_id": pid,
            "executability": "NOT-EXECUTABLE",
            "missing_element": errors[0],
            "artifact": artifact,
            "turns": spec["turns"],
            "stopping": spec["stopping"],
        }
    return {
        "record_id": pid,
        "executability": "EXECUTABLE",
        "missing_element": None,
        "artifact": {
            "name": spec["artifact_name"],
            "shape": spec["artifact_shape"],
            "keys": spec["artifact_schema_keys"],
            "produced": artifact,
        },
        "turns": spec["turns"],
        "stopping": spec["stopping"],
        "time_orientation": spec["time_orientation"],
        "core_operator": spec["core_operator"],
    }


def run_all(cases: dict | None = None) -> list[dict]:
    blob = cases if cases is not None else _load_cases()
    return [run_protocol(pid, blob[pid]) for pid in sorted(TRADECRAFT_MECHANISMS)]
