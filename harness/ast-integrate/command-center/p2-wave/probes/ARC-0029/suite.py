"""Executable A4 router regression suite for ARC-0029."""
from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent

from router import (  # noqa: E402
    reconstruct_selected,
    route,
    selected_ids,
    unbounded_select,
)

INDEX_REL = "command-center/p2-wave/probes/ARC-0029/index.json"
CORPUS_REL = "command-center/p2-wave/probes/ARC-0029/corpus.json"
REMOVED_CAP = "cap.secrets-scan"
BASELINE_EXACT_MATCH_FLOOR = 0.4


def digest_file(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def load_index(path: Path | None = None) -> dict[str, Any]:
    p = path or (HERE / "index.json")
    return json.loads(p.read_text(encoding="utf-8"))


def load_corpus(path: Path | None = None) -> dict[str, Any]:
    p = path or (HERE / "corpus.json")
    return json.loads(p.read_text(encoding="utf-8"))


def tasks_of(corpus: dict[str, Any], kind: str | None = None) -> list[dict[str, Any]]:
    rows = list(corpus.get("tasks") or [])
    if kind is None:
        return rows
    return [t for t in rows if t.get("kind") == kind]


def gold_set(task: dict[str, Any]) -> set[str]:
    return {str(x) for x in task.get("gold_ids") or []}


def recall_report(index: dict[str, Any], tasks: list[dict[str, Any]]) -> dict[str, Any]:
    labelled = [t for t in tasks if t.get("kind") == "recall"]
    hits = 0
    total = 0
    exact = 0
    per: list[dict[str, Any]] = []
    for task in labelled:
        gold = gold_set(task)
        if not gold:
            continue
        result = route(index, str(task["text"]))
        sel = set(selected_ids(result))
        hit = len(sel & gold)
        hits += hit
        total += len(gold)
        is_exact = sel == gold and result.get("verdict") == "SELECTED"
        if is_exact:
            exact += 1
        per.append(
            {
                "id": task["id"],
                "slice": task.get("slice"),
                "gold_ids": sorted(gold),
                "selected_ids": sorted(sel),
                "verdict": result.get("verdict"),
                "hits": hit,
                "gold_n": len(gold),
                "exact": is_exact,
            }
        )
    recall = (hits / total) if total else 0.0
    return {
        "task_count": len(labelled),
        "hits": hits,
        "total_gold": total,
        "recall_micro": recall,
        "exact_match_count": exact,
        "exact_match_rate": (exact / len(labelled)) if labelled else 0.0,
        "per_task": per,
    }


def fallback_report(index: dict[str, Any], tasks: list[dict[str, Any]]) -> dict[str, Any]:
    labelled = [t for t in tasks if t.get("kind") == "fallback"]
    fired = []
    missed = []
    for task in labelled:
        gold = gold_set(task)
        result = route(index, str(task["text"]))
        ok = (
            gold == set()
            and result.get("verdict") == "NO-CAPABILITY-FITS"
            and not selected_ids(result)
            and isinstance(result.get("fallback"), dict)
        )
        row = {
            "id": task["id"],
            "verdict": result.get("verdict"),
            "selected_ids": selected_ids(result),
            "pass": ok,
        }
        (fired if ok else missed).append(row)
    good = next((t for t in tasks if t.get("kind") == "recall"), None)
    silent_ok = False
    good_id = None
    if good is not None:
        gr = route(index, str(good["text"]))
        silent_ok = gr.get("verdict") == "SELECTED" and bool(selected_ids(gr))
        good_id = good["id"]
    passed = bool(labelled) and not missed and silent_ok
    return {
        "fallback_task_count": len(labelled),
        "fired": fired,
        "missed": missed,
        "silent_on_recall_task": silent_ok,
        "recall_control_id": good_id,
        "pass": passed,
    }


def flooding_report(index: dict[str, Any], task: dict[str, Any]) -> dict[str, Any]:
    bounded = route(index, str(task["text"]))
    unbounded = unbounded_select(index, str(task["text"]))
    used = int(bounded["budget"]["used"])
    ceiling = int(bounded["budget"]["ceiling"])
    max_sel = int(bounded["budget"]["max_selected"])
    b_n = len(selected_ids(bounded))
    u_n = len(selected_ids(unbounded))
    u_tokens = sum(int(r["context_tokens"]) for r in unbounded.get("selected") or [])
    refused = list(bounded["budget"].get("refused_ids") or [])
    under_token = used <= ceiling
    under_k = b_n <= max_sel
    contrast = u_tokens > ceiling and u_n > b_n
    passed = (
        bounded.get("verdict") == "SELECTED"
        and under_token
        and under_k
        and bool(refused)
        and contrast
    )
    return {
        "task_id": task["id"],
        "bounded_n": b_n,
        "bounded_tokens": used,
        "ceiling": ceiling,
        "max_selected": max_sel,
        "unbounded_n": u_n,
        "unbounded_tokens": u_tokens,
        "refused_ids": refused,
        "selected_ids": selected_ids(bounded),
        "pass": passed,
    }


def explanation_report(index: dict[str, Any], task: dict[str, Any]) -> dict[str, Any]:
    result = route(index, str(task["text"]))
    recon = reconstruct_selected(result)
    live = selected_ids(result)
    why_ok = all(row.get("matched_triggers") for row in result.get("selected") or [])
    near = result.get("near_misses") or []
    passed = recon == live and bool(live) and why_ok
    return {
        "task_id": task["id"],
        "verdict": result.get("verdict"),
        "selected_ids": live,
        "reconstructed_ids": recon,
        "reconstructs": recon == live,
        "each_selected_has_matched_triggers": why_ok,
        "near_miss_count": len(near),
        "pass": passed,
        "explanation": {
            "verdict": result.get("verdict"),
            "selected": result.get("selected"),
            "near_misses": near,
            "budget": result.get("budget"),
        },
    }


def mutation_remove_cap(
    index: dict[str, Any],
    tasks: list[dict[str, Any]],
    cap_id: str = REMOVED_CAP,
) -> dict[str, Any]:
    before = recall_report(index, tasks)
    mutant = copy.deepcopy(index)
    mutant["capabilities"] = [
        c for c in mutant.get("capabilities") or [] if str(c.get("id")) != cap_id
    ]
    after = recall_report(mutant, tasks)
    involving = 0
    for row in before.get("per_task") or []:
        if cap_id in row.get("gold_ids") and cap_id in row.get("selected_ids"):
            involving += 1
    expected_hits = int(before["hits"]) - involving
    dropped = int(before["hits"]) - int(after["hits"])
    passed = (
        involving >= 1
        and int(after["hits"]) == expected_hits
        and dropped == involving
        and int(after["hits"]) < int(before["hits"])
    )
    return {
        "removed_id": cap_id,
        "before_hits": before["hits"],
        "after_hits": after["hits"],
        "total_gold": before["total_gold"],
        "hits_involving_removed": involving,
        "expected_after_hits": expected_hits,
        "observed_drop": dropped,
        "before_recall": before["recall_micro"],
        "after_recall": after["recall_micro"],
        "pass": passed,
    }


def undercount_mutant_still_green(
    index: dict[str, Any], flood_task: dict[str, Any]
) -> dict[str, Any]:
    """Declared-token undercount: realized body >> context_tokens; flooding still uses declared cost."""
    live = flooding_report(index, flood_task)
    mutant = copy.deepcopy(index)
    for cap in mutant.get("capabilities") or []:
        cap["realized_tokens"] = int(cap.get("context_tokens") or 0) * 20
        # Intentionally leave context_tokens unchanged.
    mutant_flood = flooding_report(mutant, flood_task)
    return {
        "mutation": "realized_tokens = 20 * context_tokens; declared context_tokens unchanged",
        "live_flooding_pass": bool(live.get("pass")),
        "mutant_flooding_pass": bool(mutant_flood.get("pass")),
        "mutant_bounded_tokens_declared": mutant_flood.get("bounded_tokens"),
        "caught_by_suite": bool(live.get("pass")) and not bool(mutant_flood.get("pass")),
        "still_green": bool(mutant_flood.get("pass")),
    }


def always_top3_baseline(
    index: dict[str, Any], tasks: list[dict[str, Any]]
) -> dict[str, Any]:
    labelled = [t for t in tasks if t.get("kind") in {"recall", "fallback"}]
    freq: Counter[str] = Counter()
    for task in labelled:
        if task.get("kind") != "recall":
            continue
        for gid in gold_set(task):
            freq[gid] += 1
    top3 = [cid for cid, _ in sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))[:3]]
    exact = 0
    for task in labelled:
        gold = gold_set(task)
        if set(top3) == gold:
            exact += 1
    rate = (exact / len(labelled)) if labelled else 0.0
    return {
        "top3": top3,
        "labelled_n": len(labelled),
        "exact_match_count": exact,
        "exact_match_rate": rate,
        "below_floor": rate < BASELINE_EXACT_MATCH_FLOOR,
        "floor": BASELINE_EXACT_MATCH_FLOOR,
        "pass": rate < BASELINE_EXACT_MATCH_FLOOR,
    }


def negative_fraction(corpus: dict[str, Any]) -> float:
    labelled = [
        t
        for t in corpus.get("tasks") or []
        if t.get("kind") in {"recall", "fallback"}
    ]
    if not labelled:
        return 0.0
    neg = [t for t in labelled if not gold_set(t)]
    return len(neg) / len(labelled)


def run_suite(index: dict[str, Any] | None = None, corpus: dict[str, Any] | None = None) -> dict[str, Any]:
    idx = index if index is not None else load_index()
    corp = corpus if corpus is not None else load_corpus()
    tasks = tasks_of(corp)
    recall_tasks = [t for t in tasks if t.get("kind") == "recall"]
    fallback_tasks = [t for t in tasks if t.get("kind") == "fallback"]
    flood_task = next(t for t in tasks if t.get("kind") == "flooding")
    explain_task = next(t for t in recall_tasks if t.get("id") == "T-secret")
    held = [t for t in recall_tasks if t.get("slice") == "held_out"]
    primary = [t for t in recall_tasks if t.get("slice") == "primary"]

    recall_all = recall_report(idx, recall_tasks)
    recall_primary = recall_report(idx, primary)
    recall_held = recall_report(idx, held)
    fallback = fallback_report(idx, tasks)
    flooding = flooding_report(idx, flood_task)
    explanation = explanation_report(idx, explain_task)
    mutation = mutation_remove_cap(idx, recall_tasks)
    undercount = undercount_mutant_still_green(idx, flood_task)
    baseline = always_top3_baseline(idx, tasks)
    frac = negative_fraction(corp)

    failures: list[str] = []
    if recall_all["hits"] != recall_all["total_gold"] or recall_all["total_gold"] < 1:
        failures.append("recall-not-full")
    if recall_held["hits"] != recall_held["total_gold"] or recall_held["task_count"] < 1:
        failures.append("held-out-recall")
    if not fallback["pass"]:
        failures.append("fallback")
    if not flooding["pass"]:
        failures.append("flooding")
    if not explanation["pass"]:
        failures.append("explanation")
    if not mutation["pass"]:
        failures.append("mutation-remove")
    if not undercount["still_green"]:
        failures.append("undercount-demonstration-broke")
    if undercount["caught_by_suite"]:
        failures.append("undercount-unexpectedly-caught")
    if not baseline["pass"]:
        failures.append("corpus-too-easy")
    if frac < 0.25:
        failures.append("negative-fraction")
    if not corp.get("author_wrote_labels"):
        failures.append("author-disclosure")

    return {
        "index_sha256": digest_file(HERE / "index.json"),
        "corpus_sha256": digest_file(HERE / "corpus.json"),
        "corpus_size": len(tasks),
        "negative_query_fraction": frac,
        "recall": recall_all,
        "recall_primary": recall_primary,
        "recall_held_out": recall_held,
        "fallback": fallback,
        "flooding": flooding,
        "explanation": explanation,
        "mutation_remove": mutation,
        "undercount_gap": undercount,
        "always_top3_baseline": baseline,
        "failures": failures,
        "pass": not failures,
    }


def main() -> int:
    report = run_suite()
    print(json.dumps({k: report[k] for k in ("pass", "failures", "corpus_size", "negative_query_fraction")}, sort_keys=True))
    rec = report["recall"]
    print(
        f"recall hits={rec['hits']}/{rec['total_gold']} "
        f"held={report['recall_held_out']['hits']}/{report['recall_held_out']['total_gold']} "
        f"fallback={report['fallback']['pass']} flood={report['flooding']['pass']} "
        f"explain={report['explanation']['pass']} mut={report['mutation_remove']['pass']}"
    )
    if not report["pass"]:
        print("FAILED:ARC-0029-suite " + ",".join(report["failures"]))
        return 1
    print("SUCCESS:ARC-0029-suite")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
