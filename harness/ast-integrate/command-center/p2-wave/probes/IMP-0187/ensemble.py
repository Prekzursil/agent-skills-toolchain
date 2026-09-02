#!/usr/bin/env python3
"""Ensemble fusion: run N source workflows and aggregate by a declared typed rule.

Correlated members (agreement explained by a shared input or briefing) are not
independent evidence. Counting them as N votes is the measured failure of
counting agents instead of probes.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator

HERE = Path(__file__).resolve().parent
SCHEMA_PATH = HERE / "ensemble-fusion.schema.json"
FIXTURES = HERE / "fixtures"

AGGREGATION_RULES = frozenset(
    {"majority", "weighted", "evidence-gated", "execution-consensus"}
)


class FusionRefusal(ValueError):
    """Typed refusal: undeclared rule, empty inputs, or schema-invalid fusion."""


def canonical_hash(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def validate_fusion_doc(doc: dict) -> list[str]:
    validator = Draft7Validator(load_schema())
    return sorted({e.message for e in validator.iter_errors(doc)})


def load_fixture(name: str) -> dict:
    path = FIXTURES / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _payload_view(payload: dict, input_ids: list[str]) -> dict:
    missing = [i for i in input_ids if i not in payload]
    if missing:
        raise FusionRefusal(f"member inputs not in payload: {missing}")
    return {k: payload[k] for k in input_ids}


def _policy_echo_briefing(member: dict, payload: dict) -> Any:
    bid = member.get("briefing_id")
    if not bid or bid not in payload:
        raise FusionRefusal(f"{member['id']}: echo-briefing missing briefing")
    brief = payload[bid]
    if not isinstance(brief, dict) or "recommended" not in brief:
        raise FusionRefusal(f"{member['id']}: briefing has no recommended field")
    return brief["recommended"]


def _policy_echo_named(member: dict, payload: dict) -> Any:
    first = member["input_ids"][0]
    view = _payload_view(payload, member["input_ids"])
    item = view[first]
    if isinstance(item, dict) and "result" in item:
        return item["result"]
    return item


POLICIES = {
    "echo-briefing": _policy_echo_briefing,
    "echo-named": _policy_echo_named,
}


def run_member(member: dict, payload: dict) -> dict:
    """Execute one source workflow on the fake rail. Output is computed, not copied."""
    input_ids = list(member.get("input_ids") or [])
    if not input_ids:
        raise FusionRefusal(f"{member.get('id')}: empty input_ids is not evidence")
    policy_name = member.get("policy")
    if policy_name not in POLICIES:
        raise FusionRefusal(f"{member.get('id')}: unknown policy {policy_name!r}")
    output = POLICIES[policy_name](member, payload)
    behavior = {"primary": output}
    distinguishing = member.get("distinguishing") or {}
    if isinstance(distinguishing, dict):
        for key, slice_ in distinguishing.items():
            merged = dict(payload)
            if isinstance(slice_, dict):
                merged.update(slice_)
            behavior[str(key)] = POLICIES[policy_name](member, merged)
    return {
        "id": member["id"],
        "vendor": member.get("vendor"),
        "input_ids": input_ids,
        "briefing_id": member.get("briefing_id"),
        "output": output,
        "output_hash": canonical_hash(output),
        "weight": float(member.get("weight") or 1.0),
        "evidence_anchors": list(member.get("evidence_anchors") or []),
        "behavior": behavior,
    }


def _is_prefix(a: list[str], b: list[str]) -> bool:
    if not a or not b:
        return False
    n = min(len(a), len(b))
    return list(a[:n]) == list(b[:n])


def shared_inputs(a: dict, b: dict) -> list[str]:
    """Signals that two members are not independent probes.

    Shared briefing, set overlap, or identical input prefix each reduce N.
    """
    shared: set[str] = set(a["input_ids"]) & set(b["input_ids"])
    ba, bb = a.get("briefing_id"), b.get("briefing_id")
    if ba and ba == bb:
        shared.add(f"briefing:{ba}")
    if _is_prefix(a["input_ids"], b["input_ids"]):
        shared.add("identical-prefix")
    return sorted(shared)


class _UnionFind:
    def __init__(self, ids: list[str]) -> None:
        self.parent = {i: i for i in ids}

    def find(self, x: str) -> str:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def assess_independence(runs: list[dict]) -> dict:
    """Flag an ensemble whose agreement is explained by shared input.

    Verdict is non-independent iff at least one pair both agrees and shares input.
    Members that agree on disjoint inputs are independent corroboration.
    """
    if len(runs) < 2:
        raise FusionRefusal("ensemble requires N>=2 source workflows")
    pairs = []
    uf = _UnionFind([r["id"] for r in runs])
    flagged: set[str] = set()
    for i, a in enumerate(runs):
        for b in runs[i + 1 :]:
            shared = shared_inputs(a, b)
            agreed = a["output_hash"] == b["output_hash"]
            rec = {"a": a["id"], "b": b["id"], "agreed": agreed, "shared": shared}
            pairs.append(rec)
            if agreed and shared:
                flagged.add(a["id"])
                flagged.add(b["id"])
                uf.union(a["id"], b["id"])
    roots = {uf.find(r["id"]) for r in runs}
    verdict = "non-independent" if flagged else "independent"
    return {
        "verdict": verdict,
        "raw_n": len(runs),
        "effective_n": len(roots),
        "flagged_member_ids": sorted(flagged),
        "correlated_pairs": pairs,
        "_clusters": _clusters(runs, uf),
    }


def _clusters(runs: list[dict], uf: _UnionFind) -> list[list[dict]]:
    buckets: dict[str, list[dict]] = {}
    for r in runs:
        buckets.setdefault(uf.find(r["id"]), []).append(r)
    return [buckets[k] for k in sorted(buckets)]


def _declare_rule(aggregation: Any) -> dict:
    if not isinstance(aggregation, dict) or "rule" not in aggregation:
        raise FusionRefusal("aggregation.rule is required and must be declared")
    rule = aggregation["rule"]
    if rule not in AGGREGATION_RULES:
        raise FusionRefusal(
            f"aggregation.rule must be one of {sorted(AGGREGATION_RULES)}, got {rule!r}"
        )
    if rule == "weighted" and not isinstance(aggregation.get("weights"), dict):
        raise FusionRefusal("weighted aggregation requires weights")
    if rule == "evidence-gated" and int(aggregation.get("min_anchors") or 0) < 1:
        raise FusionRefusal("evidence-gated aggregation requires min_anchors>=1")
    if rule == "execution-consensus":
        di = aggregation.get("distinguishing_inputs")
        if not isinstance(di, list) or not di:
            raise FusionRefusal(
                "execution-consensus requires distinguishing_inputs"
            )
    return aggregation


def _eligible(runs: list[dict], aggregation: dict) -> list[dict]:
    rule = aggregation["rule"]
    if rule != "evidence-gated":
        return list(runs)
    min_anchors = int(aggregation["min_anchors"])
    return [r for r in runs if len(r.get("evidence_anchors") or []) >= min_anchors]


def _choice_key(run: dict, aggregation: dict) -> str:
    if aggregation["rule"] != "execution-consensus":
        return run["output_hash"]
    keys = list(aggregation["distinguishing_inputs"])
    observed = tuple(run.get("behavior", {}).get(k, run["output"]) for k in keys)
    return canonical_hash(observed)


def _cluster_mass(cluster: list[dict], aggregation: dict) -> float:
    """Correlated members contribute one mass, not N masses."""
    if aggregation["rule"] == "weighted":
        weights = aggregation["weights"]
        return max(float(weights.get(m["id"], m["weight"])) for m in cluster)
    return 1.0


def _tally(clusters: list[list[dict]], aggregation: dict) -> tuple[Any, list[dict], str]:
    votes: dict[str, dict] = {}
    for cluster in clusters:
        key = _choice_key(cluster[0], aggregation)
        mass = _cluster_mass(cluster, aggregation)
        bucket = votes.setdefault(
            key,
            {
                "choice": cluster[0]["output"],
                "mass": 0.0,
                "member_ids": [],
                "cluster_id": key[:12],
            },
        )
        bucket["mass"] += mass
        bucket["member_ids"].extend(m["id"] for m in cluster)
        # execution-consensus choice is the behavior cluster label's primary output
        if aggregation["rule"] == "execution-consensus":
            bucket["choice"] = cluster[0]["output"]
    rows = [
        {
            "cluster_id": v["cluster_id"],
            "member_ids": sorted(v["member_ids"]),
            "choice": v["choice"],
            "mass": v["mass"],
        }
        for v in votes.values()
    ]
    rows.sort(key=lambda r: (-float(r["mass"]), str(r["cluster_id"])))
    if not rows:
        return None, rows, "no-eligible-members"
    top = rows[0]["mass"]
    winners = [r for r in rows if r["mass"] == top]
    if len(winners) > 1:
        return None, rows, "tie-UNRESOLVED"
    return winners[0]["choice"], rows, "ok"


def fuse(
    fixture: dict,
    aggregation: dict,
    *,
    postcondition: Any | None = None,
) -> dict:
    """Run N sources, flag correlated agreement, aggregate by the declared rule."""
    aggregation = _declare_rule(deepcopy(aggregation))
    payload = fixture["payload"]
    runs = [run_member(m, payload) for m in fixture["members"]]
    independence = assess_independence(runs)
    eligible = _eligible(runs, aggregation)
    if not eligible:
        result = {
            "verdict": None,
            "rule": aggregation["rule"],
            "reason": "no-eligible-members",
            "cluster_votes": [],
            "collapsed_correlated_mass": independence["verdict"] == "non-independent",
        }
        clusters: list[list[dict]] = []
    else:
        # Re-cluster the eligible set so evidence-gated drops do not keep ghosts.
        independence_elig = assess_independence(eligible) if len(eligible) >= 2 else {
            "verdict": "independent",
            "raw_n": len(eligible),
            "effective_n": len(eligible),
            "flagged_member_ids": [],
            "correlated_pairs": [],
            "_clusters": [eligible],
        }
        clusters = independence_elig["_clusters"]
        verdict, rows, reason = _tally(clusters, aggregation)
        result = {
            "verdict": verdict,
            "rule": aggregation["rule"],
            "reason": reason,
            "cluster_votes": rows,
            "collapsed_correlated_mass": independence["verdict"] == "non-independent",
        }
    if postcondition is not None:
        applied = True
        passed = result["verdict"] == postcondition
        result["postcondition"] = {
            "applied": applied,
            "passed": passed,
            "note": (
                "unanimous consensus is still wrong when the postcondition fails; "
                "agreement is not a substitute for a probe"
            ),
        }
    independence_out = {
        k: independence[k]
        for k in (
            "verdict",
            "raw_n",
            "effective_n",
            "flagged_member_ids",
            "correlated_pairs",
        )
    }
    sources = [
        {
            "id": r["id"],
            "vendor": r.get("vendor"),
            "input_ids": r["input_ids"],
            "briefing_id": r.get("briefing_id"),
            "output": r["output"],
            "output_hash": r["output_hash"],
            "weight": r["weight"],
            "evidence_anchors": r["evidence_anchors"],
            "behavior": r["behavior"],
        }
        for r in runs
    ]
    doc = {
        "strategy": "ensemble",
        "aggregation": aggregation,
        "sources": sources,
        "independence": independence_out,
        "result": result,
        "lineage": {
            "source_ids": [r["id"] for r in runs],
            "fusion_strategy": "ensemble",
        },
    }
    errors = validate_fusion_doc(doc)
    if errors:
        raise FusionRefusal("emitted fusion failed schema: " + "; ".join(errors[:8]))
    return doc


def plant_shared_briefing(fixture: dict, briefing_id: str = "planted.shared") -> dict:
    """Detector control: copy a briefing onto otherwise-independent members."""
    planted = deepcopy(fixture)
    planted["id"] = fixture["id"] + ".planted-shared-briefing"
    planted["payload"] = dict(fixture["payload"])
    planted["payload"][briefing_id] = {"recommended": "ACCEPT"}
    for member in planted["members"]:
        member["briefing_id"] = briefing_id
    return planted


def naive_majority_without_collapse(runs: list[dict]) -> Any:
    """The forbidden counter: count agents, not independent probes."""
    counts: dict[str, tuple[int, Any]] = {}
    for r in runs:
        n, choice = counts.get(r["output_hash"], (0, r["output"]))
        counts[r["output_hash"]] = (n + 1, choice)
    return max(counts.values(), key=lambda t: t[0])[1]


def evaluate_correlation_contract() -> dict:
    correlated = load_fixture("correlated")
    independent = load_fixture("independent")
    agg = {"rule": "majority"}
    corr = fuse(correlated, agg)
    indep = fuse(independent, agg)
    planted = fuse(plant_shared_briefing(independent), agg)
    corr_flagged = corr["independence"]["verdict"] == "non-independent"
    indep_clean = indep["independence"]["verdict"] == "independent"
    plant_fires = planted["independence"]["verdict"] == "non-independent"
    # Collapse must change the correlated ensemble's effective N.
    collapsed = corr["independence"]["effective_n"] < corr["independence"]["raw_n"]
    naive = naive_majority_without_collapse(corr["sources"])
    return {
        "correlated_flagged": corr_flagged,
        "independent_not_flagged": indep_clean,
        "planted_shared_briefing_flagged": plant_fires,
        "effective_n_collapsed": collapsed,
        "correlated_raw_n": corr["independence"]["raw_n"],
        "correlated_effective_n": corr["independence"]["effective_n"],
        "independent_raw_n": indep["independence"]["raw_n"],
        "independent_effective_n": indep["independence"]["effective_n"],
        "correlated_pairs": corr["independence"]["correlated_pairs"],
        "independent_flagged_ids": indep["independence"]["flagged_member_ids"],
        "naive_count_agents_choice": naive,
        "collapsed_choice": corr["result"]["verdict"],
        "both_states": corr_flagged and indep_clean and plant_fires and collapsed,
        "correlated_fusion": corr,
        "independent_fusion": indep,
    }


def evaluate_schema_contract() -> dict:
    fixture = load_fixture("independent")
    rules = [
        {"rule": "majority"},
        {
            "rule": "weighted",
            "weights": {"wf.static": 0.5, "wf.runtime": 0.3, "wf.schema": 0.2},
        },
        {"rule": "evidence-gated", "min_anchors": 1},
        {
            "rule": "execution-consensus",
            "distinguishing_inputs": ["primary"],
        },
    ]
    validated = []
    for agg in rules:
        doc = fuse(fixture, agg)
        errs = validate_fusion_doc(doc)
        validated.append(
            {
                "rule": agg["rule"],
                "schema_errors": errs,
                "ok": not errs and doc["aggregation"]["rule"] == agg["rule"],
                "verdict": doc["result"]["verdict"],
            }
        )
    undeclared_refused = False
    undeclared_msg = ""
    try:
        fuse(fixture, {})
    except FusionRefusal as exc:
        undeclared_refused = "rule is required" in str(exc)
        undeclared_msg = str(exc)
    invalid_refused = False
    invalid_msg = ""
    try:
        fuse(fixture, {"rule": "average"})
    except FusionRefusal as exc:
        invalid_refused = "must be one of" in str(exc)
        invalid_msg = str(exc)
    missing_rule_doc = {
        "strategy": "ensemble",
        "aggregation": {},
        "sources": fuse(fixture, {"rule": "majority"})["sources"],
        "independence": fuse(fixture, {"rule": "majority"})["independence"],
        "result": fuse(fixture, {"rule": "majority"})["result"],
        "lineage": fuse(fixture, {"rule": "majority"})["lineage"],
    }
    missing_rule_errors = validate_fusion_doc(missing_rule_doc)
    evidence = fuse(
        load_fixture("evidence-asymmetric"),
        {"rule": "evidence-gated", "min_anchors": 1},
    )
    majority_on_asymmetric = fuse(
        load_fixture("evidence-asymmetric"),
        {"rule": "majority"},
    )
    all_rules_ok = all(row["ok"] for row in validated)
    return {
        "all_four_rules_schema_valid": all_rules_ok,
        "rules": validated,
        "undeclared_refused": undeclared_refused,
        "undeclared_msg": undeclared_msg,
        "invalid_rule_refused": invalid_refused,
        "invalid_rule_msg": invalid_msg,
        "missing_rule_schema_errors": missing_rule_errors,
        "missing_rule_schema_rejects": bool(missing_rule_errors),
        "evidence_gated_choice": evidence["result"]["verdict"],
        "evidence_gated_eligible": [
            s["id"]
            for s in evidence["sources"]
            if s["evidence_anchors"]
        ],
        "majority_on_asymmetric_choice": majority_on_asymmetric["result"]["verdict"],
        "naive_count_agents_on_asymmetric": naive_majority_without_collapse(
            majority_on_asymmetric["sources"]
        ),
        "evidence_gated_ignores_uncited_majority": (
            evidence["result"]["verdict"] == "REJECT"
            and naive_majority_without_collapse(majority_on_asymmetric["sources"])
            == "ACCEPT"
        ),
        "pass": (
            all_rules_ok
            and undeclared_refused
            and invalid_refused
            and bool(missing_rule_errors)
            and evidence["result"]["verdict"] == "REJECT"
            and naive_majority_without_collapse(majority_on_asymmetric["sources"])
            == "ACCEPT"
        ),
    }
