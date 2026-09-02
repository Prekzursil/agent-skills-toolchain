#!/usr/bin/env python3
"""Ensemble fusion by execution consensus (WFA-0105).

Runs several sources on the same distinguishing inputs and reconciles by
behavioural clustering over produced artifacts. Cluster mass is the number of
distinct vendors in the cluster: Anthropic/OpenAI agreement is independent
signal; two same-vendor members agreeing is one signal wearing two hats.

Never ranks outputs by a model opinion of quality. A cluster-mass tie is
UNRESOLVED. Unanimous agreement that fails the postcondition is not hidden.
"""
from __future__ import annotations

import ast
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
SCHEMA_PATH = HERE / "fusion-result.schema.json"

POLICIES = frozenset({"unique-sorted", "order-preserving", "planted-wrong"})
FORBIDDEN_IMPORT_ROOTS = frozenset(
    {"openai", "anthropic", "httpx", "requests", "aiohttp", "litellm"}
)
FORBIDDEN_NAME_FRAGMENTS = (
    "rank_by_quality",
    "llm_rank",
    "model_opinion",
    "chat_completions",
    "quality_score_llm",
)


class FusionRefusal(ValueError):
    """Typed refusal: empty ensemble, unknown source, or undeclared policy."""


def canonical_dumps(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def canonical_hash(obj: Any) -> str:
    return hashlib.sha256(canonical_dumps(obj).encode("utf-8")).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def distinguishing_inputs() -> list[dict]:
    doc = load_json(FIXTURES / "inputs.json")
    rows = list(doc.get("distinguishing_inputs") or [])
    if len(rows) < 2:
        raise FusionRefusal("execution-consensus requires >=2 distinguishing inputs")
    ids = [r.get("id") for r in rows]
    if any(not isinstance(i, str) or not i for i in ids):
        raise FusionRefusal("distinguishing input id missing")
    if len(set(ids)) != len(ids):
        raise FusionRefusal(f"duplicate distinguishing input ids: {ids}")
    return rows


def source_catalog() -> dict[str, dict]:
    rows = list(load_json(FIXTURES / "sources.json").get("sources") or [])
    out: dict[str, dict] = {}
    for row in rows:
        sid = row.get("id")
        if not isinstance(sid, str) or not sid:
            raise FusionRefusal("source id missing")
        if sid in out:
            raise FusionRefusal(f"duplicate source id {sid}")
        vendor = row.get("vendor")
        policy = row.get("policy")
        if vendor not in {"anthropic", "openai"}:
            raise FusionRefusal(f"{sid}: vendor must be anthropic|openai, got {vendor!r}")
        if policy not in POLICIES:
            raise FusionRefusal(f"{sid}: unknown policy {policy!r}")
        out[sid] = {"id": sid, "vendor": vendor, "policy": policy}
    if len(out) < 2:
        raise FusionRefusal("catalog must declare >=2 sources")
    return out


def ensemble_catalog() -> dict[str, dict]:
    return dict(load_json(FIXTURES / "ensembles.json").get("ensembles") or {})


def _unique_sorted(tokens: list[str]) -> dict:
    return {"tokens": sorted({t.lower() for t in tokens})}


def _order_preserving(tokens: list[str]) -> dict:
    return {"tokens": [t.lower() for t in tokens]}


def _planted_wrong(tokens: list[str]) -> dict:
    del tokens
    return {"tokens": ["PLANTED-WRONG"]}


POLICY_FNS: dict[str, Callable[[list[str]], dict]] = {
    "unique-sorted": _unique_sorted,
    "order-preserving": _order_preserving,
    "planted-wrong": _planted_wrong,
}


def execute_source(source: dict, case: dict) -> dict:
    """Produce an artifact from one source on one input. No ranking step."""
    tokens = list(case.get("tokens") or [])
    if not isinstance(tokens, list) or not all(isinstance(t, str) for t in tokens):
        raise FusionRefusal(f"{source['id']}: input tokens must be a string list")
    fn = POLICY_FNS.get(source["policy"])
    if fn is None:
        raise FusionRefusal(f"{source['id']}: undeclared policy {source['policy']!r}")
    artifact = fn(tokens)
    return {
        "source_id": source["id"],
        "vendor": source["vendor"],
        "policy": source["policy"],
        "input_id": case["id"],
        "artifact": artifact,
        "artifact_hash": canonical_hash(artifact),
    }


def _run_one_source_all_inputs(source: dict, cases: list[dict]) -> dict:
    per_input = {}
    for case in cases:
        per_input[case["id"]] = execute_source(source, case)
    fingerprints = tuple(per_input[c["id"]]["artifact_hash"] for c in cases)
    return {
        "id": source["id"],
        "vendor": source["vendor"],
        "policy": source["policy"],
        "per_input": per_input,
        "behavior_fingerprint": canonical_hash(list(fingerprints)),
        "primary_artifact": per_input[cases[0]["id"]]["artifact"],
        "primary_artifact_hash": per_input[cases[0]["id"]]["artifact_hash"],
        "primary_input_id": cases[0]["id"],
    }


def run_sources_parallel(sources: list[dict], cases: list[dict]) -> list[dict]:
    """Submit every source before waiting. Local threads stand in for parallel arms."""
    if len(sources) < 2:
        raise FusionRefusal("ensemble requires N>=2 sources")
    runs: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=len(sources)) as pool:
        futs = {
            pool.submit(_run_one_source_all_inputs, src, cases): src["id"]
            for src in sources
        }
        for fut in as_completed(futs):
            sid = futs[fut]
            runs[sid] = fut.result()
    return [runs[s["id"]] for s in sources]


def postcondition(case: dict, artifact: dict) -> dict:
    """Execution probe: output tokens must be derived from the input vocab.

    Invented tokens (the planted-wrong constant) fail. Consensus cannot skip this.
    """
    tokens = list(case.get("tokens") or [])
    vocab = {t.lower() for t in tokens}
    out = artifact.get("tokens") if isinstance(artifact, dict) else None
    if not isinstance(out, list) or not all(isinstance(x, str) for x in out):
        return {"passed": False, "reason": "tokens-not-string-list"}
    if tokens and not out:
        return {"passed": False, "reason": "empty-output-for-nonempty-input"}
    invented = [t for t in out if t.lower() not in vocab]
    if invented:
        return {
            "passed": False,
            "reason": "invented-tokens",
            "invented": invented,
        }
    return {"passed": True, "reason": "derived-from-input-vocab"}


def cluster_runs(runs: list[dict]) -> list[dict]:
    buckets: dict[str, list[dict]] = {}
    order: list[str] = []
    for run in runs:
        key = run["behavior_fingerprint"]
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append(run)
    clusters = []
    for i, key in enumerate(order, 1):
        members = buckets[key]
        vendors = sorted({m["vendor"] for m in members})
        clusters.append(
            {
                "cluster_id": f"C{i}-{key[:12]}",
                "behavior_fingerprint": key,
                "member_ids": [m["id"] for m in members],
                "vendors": vendors,
                "vendor_mass": len(vendors),
                "member_count": len(members),
                "choice": members[0]["primary_artifact"],
                "choice_hash": members[0]["primary_artifact_hash"],
                "same_vendor_collapsed": len(members) > len(vendors),
            }
        )
    return clusters


def assign_clusters(runs: list[dict], clusters: list[dict]) -> list[dict]:
    by_fp = {c["behavior_fingerprint"]: c["cluster_id"] for c in clusters}
    assigned = []
    for run in runs:
        row = {
            "id": run["id"],
            "vendor": run["vendor"],
            "policy": run["policy"],
            "cluster_id": by_fp[run["behavior_fingerprint"]],
            "behavior_fingerprint": run["behavior_fingerprint"],
            "primary_artifact": run["primary_artifact"],
            "primary_artifact_hash": run["primary_artifact_hash"],
            "per_input": {
                iid: {
                    "artifact": rec["artifact"],
                    "artifact_hash": rec["artifact_hash"],
                }
                for iid, rec in run["per_input"].items()
            },
        }
        assigned.append(row)
    return assigned


def independence_pairs(runs: list[dict]) -> list[dict]:
    pairs = []
    for i, a in enumerate(runs):
        for b in runs[i + 1 :]:
            agreed = a["behavior_fingerprint"] == b["behavior_fingerprint"]
            cross = a["vendor"] != b["vendor"]
            pairs.append(
                {
                    "a": a["id"],
                    "b": b["id"],
                    "agreed": agreed,
                    "cross_vendor": cross,
                    "signal": (
                        "cross-vendor-independent"
                        if agreed and cross
                        else "same-vendor-one-signal"
                        if agreed and not cross
                        else "disagreement"
                    ),
                }
            )
    return pairs


def reconcile(clusters: list[dict]) -> dict:
    if not clusters:
        return {
            "verdict": "UNRESOLVED",
            "reason": "no-clusters",
            "winner_cluster_id": None,
            "tied_cluster_ids": [],
            "llm_ranking_invocations": 0,
        }
    ranked = sorted(
        clusters, key=lambda c: (-int(c["vendor_mass"]), str(c["cluster_id"]))
    )
    top = ranked[0]["vendor_mass"]
    winners = [c for c in ranked if c["vendor_mass"] == top]
    if len(winners) > 1:
        return {
            "verdict": "UNRESOLVED",
            "reason": "cluster-mass-tie",
            "winner_cluster_id": None,
            "tied_cluster_ids": [c["cluster_id"] for c in winners],
            "llm_ranking_invocations": 0,
        }
    return {
        "verdict": "RESOLVED",
        "reason": "unique-max-vendor-mass",
        "winner_cluster_id": winners[0]["cluster_id"],
        "tied_cluster_ids": [],
        "llm_ranking_invocations": 0,
    }


def apply_postcondition(
    result: dict, winner: dict | None, cases: list[dict], runs: list[dict]
) -> dict:
    """Unanimous (or winning) consensus is still wrong when this probe fails."""
    if result["verdict"] != "RESOLVED" or winner is None:
        return {
            "applied": False,
            "passed": None,
            "note": "postcondition applies to a unique winner, not to a tie",
            "per_input": [],
        }
    members = [r for r in runs if r["id"] in winner["member_ids"]]
    per_input = []
    passed_all = True
    for case in cases:
        # Probe the cluster choice: every member already matched on this input.
        sample = members[0]["per_input"][case["id"]]["artifact"]
        pc = postcondition(case, sample)
        per_input.append(
            {
                "input_id": case["id"],
                "passed": pc["passed"],
                "reason": pc["reason"],
                "invented": pc.get("invented") or [],
            }
        )
        if not pc["passed"]:
            passed_all = False
    out = {
        "applied": True,
        "passed": passed_all,
        "note": (
            "unanimous consensus is still wrong when the postcondition fails; "
            "agreement is not a substitute for a probe"
        ),
        "per_input": per_input,
    }
    if not passed_all:
        result["verdict"] = "POSTCONDITION-FAILED"
        result["reason"] = "winner-failed-postcondition"
    return out


def naive_member_count_winner(clusters: list[dict]) -> dict:
    """Forbidden counter: count agents, not independent vendor signals."""
    ranked = sorted(
        clusters, key=lambda c: (-int(c["member_count"]), str(c["cluster_id"]))
    )
    top = ranked[0]["member_count"]
    winners = [c for c in ranked if c["member_count"] == top]
    if len(winners) > 1:
        return {
            "verdict": "UNRESOLVED",
            "winner_cluster_id": None,
            "tied_cluster_ids": [c["cluster_id"] for c in winners],
            "rule": "naive-member-count",
        }
    return {
        "verdict": "RESOLVED",
        "winner_cluster_id": winners[0]["cluster_id"],
        "tied_cluster_ids": [],
        "rule": "naive-member-count",
        "choice": winners[0]["choice"],
    }


def single_input_clusters(runs: list[dict], input_id: str) -> dict[str, str]:
    """What clustering would do if it looked only at one input (control)."""
    buckets: dict[str, str] = {}
    labels: dict[str, str] = {}
    n = 0
    for run in runs:
        h = run["per_input"][input_id]["artifact_hash"]
        if h not in labels:
            n += 1
            labels[h] = f"S{n}"
        buckets[run["id"]] = labels[h]
    return buckets


def fuse(ensemble_id: str) -> dict:
    ensembles = ensemble_catalog()
    if ensemble_id not in ensembles:
        raise FusionRefusal(f"unknown ensemble {ensemble_id!r}")
    spec = ensembles[ensemble_id]
    catalog = source_catalog()
    ids = list(spec.get("source_ids") or [])
    if len(ids) < 2:
        raise FusionRefusal(f"{ensemble_id}: ensemble requires N>=2 sources")
    missing = [i for i in ids if i not in catalog]
    if missing:
        raise FusionRefusal(f"{ensemble_id}: unknown sources {missing}")
    sources = [catalog[i] for i in ids]
    cases = distinguishing_inputs()
    runs = run_sources_parallel(sources, cases)
    clusters = cluster_runs(runs)
    assigned = assign_clusters(runs, clusters)
    result = reconcile(clusters)
    winner = next(
        (c for c in clusters if c["cluster_id"] == result["winner_cluster_id"]),
        None,
    )
    post = apply_postcondition(result, winner, cases, runs)
    pairs = independence_pairs(runs)
    naive = naive_member_count_winner(clusters)
    agree_sorted = single_input_clusters(runs, "case.already-sorted")
    return {
        "ensemble_id": ensemble_id,
        "strategy": "ensemble",
        "reconcile_by": "execution-consensus",
        "distinguishing_input_ids": [c["id"] for c in cases],
        "sources": assigned,
        "clusters": clusters,
        "independence": {
            "rule": (
                "cross-vendor agreement is independent signal; "
                "same-vendor agreement is one signal wearing two hats"
            ),
            "pairs": pairs,
            "raw_n": len(runs),
            "cluster_count": len(clusters),
            "effective_vendor_mass": sum(c["vendor_mass"] for c in clusters),
        },
        "result": result,
        "postcondition": post,
        "naive_member_count": naive,
        "single_input_control": {
            "input_id": "case.already-sorted",
            "note": (
                "unique-sorted and order-preserving agree on this input; "
                "execution-consensus still splits them using the full set"
            ),
            "assignment": agree_sorted,
        },
        "lineage": {
            "source_ids": ids,
            "fusion_strategy": "ensemble",
        },
        "llm_ranking_invocations": 0,
    }


def _ast_simple_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def scan_operator_for_llm_ranking(path: Path | None = None) -> dict:
    """AST proof: no LLM client import, no rank-by-quality def or call.

    Names are collected from the AST so this scanner's own forbidden-name
    constants cannot self-hit a raw-text grep.
    """
    target = path or (HERE / "ensemble_operator.py")
    text = target.read_text(encoding="utf-8")
    tree = ast.parse(text)
    imports: list[str] = []
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module.split(".")[0])
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.append(node.name)
        elif isinstance(node, ast.Call):
            called = _ast_simple_name(node.func)
            if called:
                names.append(called)
        elif isinstance(node, ast.Name):
            names.append(node.id)
    bad_imports = sorted({n for n in imports if n in FORBIDDEN_IMPORT_ROOTS})
    forbidden = set(FORBIDDEN_NAME_FRAGMENTS)
    bad_names = sorted({n for n in names if n in forbidden})
    return {
        "path": target.relative_to(HERE.parents[3]).as_posix()
        if HERE.parents[3] in target.parents
        else str(target),
        "imports": sorted(set(imports)),
        "forbidden_imports": bad_imports,
        "forbidden_name_hits": bad_names,
        "llm_ranking_absent": not bad_imports and not bad_names,
    }


def evaluate_contracts() -> dict:
    xv = fuse("cross-vendor-consensus")
    sv = fuse("same-vendor-tie")
    uw = fuse("unanimous-wrong")
    tm = fuse("equal-mass-tie")
    scan = scan_operator_for_llm_ranking()

    xv_winner = next(
        c for c in xv["clusters"] if c["cluster_id"] == xv["result"]["winner_cluster_id"]
    )
    unique_sorted_ids = {
        s["id"] for s in xv["sources"] if s["policy"] == "unique-sorted"
    }
    xv_members = set(xv_winner["member_ids"])

    # Distinguishing-input control: families agree on already-sorted, disagree overall.
    us = next(s for s in xv["sources"] if s["id"] == "wf.anthropic.unique-sorted")
    op = next(s for s in xv["sources"] if s["id"] == "wf.openai.order-preserving")
    agree_sorted = (
        us["per_input"]["case.already-sorted"]["artifact_hash"]
        == op["per_input"]["case.already-sorted"]["artifact_hash"]
    )
    disagree_mixed = (
        us["per_input"]["case.mixed-dup"]["artifact_hash"]
        != op["per_input"]["case.mixed-dup"]["artifact_hash"]
    )
    split_despite_sorted_agreement = us["cluster_id"] != op["cluster_id"]

    naive_breaks_sv = (
        sv["naive_member_count"]["verdict"] == "RESOLVED"
        and sv["result"]["verdict"] == "UNRESOLVED"
    )
    same_vendor_pair = any(
        p["signal"] == "same-vendor-one-signal" for p in xv["independence"]["pairs"]
    )
    cross_vendor_pair = any(
        p["signal"] == "cross-vendor-independent" for p in xv["independence"]["pairs"]
    )
    xv_mass_is_vendors = xv_winner["vendor_mass"] == 2 and xv_winner["member_count"] == 3

    both_states_post = (
        xv["result"]["verdict"] == "RESOLVED"
        and xv["postcondition"]["passed"] is True
        and uw["result"]["verdict"] == "POSTCONDITION-FAILED"
        and uw["postcondition"]["passed"] is False
    )
    return {
        "cross_vendor": xv,
        "same_vendor_tie": sv,
        "unanimous_wrong": uw,
        "equal_mass_tie": tm,
        "llm_scan": scan,
        "genuine_consensus_resolved": xv["result"]["verdict"] == "RESOLVED",
        "genuine_consensus_postcondition_passed": xv["postcondition"]["passed"] is True,
        "winner_is_unique_sorted": unique_sorted_ids == xv_members,
        "cross_vendor_mass_two_not_three": xv_mass_is_vendors,
        "same_vendor_pair_collapsed": same_vendor_pair,
        "cross_vendor_pair_independent": cross_vendor_pair,
        "same_vendor_tie_unresolved": sv["result"]["verdict"] == "UNRESOLVED",
        "equal_mass_tie_unresolved": tm["result"]["verdict"] == "UNRESOLVED",
        "naive_member_count_breaks_same_vendor_tie": naive_breaks_sv,
        "unanimous_wrong_postcondition_failed": uw["result"]["verdict"]
        == "POSTCONDITION-FAILED",
        "unanimous_cluster_count": len(uw["clusters"]),
        "agree_on_already_sorted": agree_sorted,
        "disagree_on_mixed_dup": disagree_mixed,
        "split_despite_sorted_agreement": split_despite_sorted_agreement,
        "llm_ranking_absent": scan["llm_ranking_absent"],
        "llm_ranking_invocations": xv["llm_ranking_invocations"],
        "both_states_postcondition": both_states_post,
        "pass": (
            both_states_post
            and unique_sorted_ids == xv_members
            and xv_mass_is_vendors
            and same_vendor_pair
            and cross_vendor_pair
            and sv["result"]["verdict"] == "UNRESOLVED"
            and tm["result"]["verdict"] == "UNRESOLVED"
            and naive_breaks_sv
            and agree_sorted
            and disagree_mixed
            and split_despite_sorted_agreement
            and scan["llm_ranking_absent"]
            and xv["llm_ranking_invocations"] == 0
        ),
    }


def public_source_row(row: dict) -> dict:
    return deepcopy(row)


if __name__ == "__main__":
    report = evaluate_contracts()
    summary = {k: v for k, v in report.items() if k not in {
        "cross_vendor",
        "same_vendor_tie",
        "unanimous_wrong",
        "equal_mass_tie",
        "llm_scan",
    }}
    print(canonical_dumps(summary))
    print("pass=" + str(report["pass"]))
    raise SystemExit(0 if report["pass"] else 1)
