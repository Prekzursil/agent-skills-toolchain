"""Live conflict-resolution measurement on one shared task set."""
from __future__ import annotations

import hashlib
import json
import random
from typing import Any, Callable

from contract import ALL_STRATEGIES, ASK, NAMED_STRATEGIES
from fixtures import SKILLS, TASKS, Skill, Task

Resolver = Callable[[list[Skill], Task], str]


def cwd_in_scope(cwd: str, prefix: str) -> bool:
    if not prefix:
        return True
    c = cwd.replace("\\", "/").rstrip("/") + "/"
    p = prefix.replace("\\", "/").rstrip("/") + "/"
    return c.startswith(p)


def trigger_hits(query: str, skill: Skill) -> list[str]:
    """Whole-phrase hits; 'test' must not match inside 'pytest'."""
    import re

    q = query.lower()
    hits = []
    for trig in skill["triggers"]:
        t = str(trig).lower()
        if not t:
            continue
        pat = r"(?<![a-z0-9])" + re.escape(t) + r"(?![a-z0-9])"
        if re.search(pat, q):
            hits.append(t)
    return hits


def specificity_score(query: str, skill: Skill) -> tuple[int, int]:
    hits = trigger_hits(query, skill)
    if not hits:
        return (0, 0)
    best = max(hits, key=lambda t: (len(t.split()), len(t)))
    return (len(best.split()), len(best))


def matching_skills(task: Task, skills: tuple[Skill, ...] = SKILLS) -> list[Skill]:
    cwd = str(task.get("cwd") or "")
    query = str(task.get("query") or "")
    out: list[Skill] = []
    for skill in skills:
        if not cwd_in_scope(cwd, str(skill.get("cwd_prefix") or "")):
            continue
        if trigger_hits(query, skill):
            out.append(skill)
    return out


def _lex_min(skills: list[Skill]) -> str:
    return sorted(s["id"] for s in skills)[0]


def resolve_specificity(matches: list[Skill], task: Task) -> str:
    if not matches:
        return ASK
    if len(matches) == 1:
        return str(matches[0]["id"])
    scored = [(specificity_score(str(task["query"]), s), s) for s in matches]
    best = max(scored, key=lambda x: x[0])[0]
    winners = [s for sc, s in scored if sc == best]
    if len(winners) == 1:
        return str(winners[0]["id"])
    return _lex_min(winners)


def resolve_scope_depth(matches: list[Skill], task: Task) -> str:
    if not matches:
        return ASK
    if len(matches) == 1:
        return str(matches[0]["id"])
    best = max(int(s["scope_depth"]) for s in matches)
    winners = [s for s in matches if int(s["scope_depth"]) == best]
    if len(winners) == 1:
        return str(winners[0]["id"])
    return _lex_min(winners)


def resolve_explicit_priority(matches: list[Skill], task: Task) -> str:
    if not matches:
        return ASK
    if len(matches) == 1:
        return str(matches[0]["id"])
    best = max(int(s["priority"]) for s in matches)
    winners = [s for s in matches if int(s["priority"]) == best]
    if len(winners) == 1:
        return str(winners[0]["id"])
    return _lex_min(winners)


def resolve_ask_the_user(matches: list[Skill], task: Task) -> str:
    if not matches:
        return ASK
    if len(matches) == 1:
        return str(matches[0]["id"])
    return ASK


def resolve_random(matches: list[Skill], task: Task) -> str:
    """Deliberately uninformed: uniform draw from the full catalog."""
    rng = random.Random(_task_seed(str(task["id"])))
    return str(rng.choice(sorted(s["id"] for s in SKILLS)))


def _task_seed(task_id: str) -> int:
    digest = hashlib.sha256(f"RES-0105:{task_id}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


RESOLVERS: dict[str, Resolver] = {
    "specificity": resolve_specificity,
    "scope_depth": resolve_scope_depth,
    "explicit_priority": resolve_explicit_priority,
    "ask_the_user": resolve_ask_the_user,
    "random": resolve_random,
}


def pick(strategy: str, task: Task) -> dict[str, Any]:
    matches = matching_skills(task)
    chosen = RESOLVERS[strategy](matches, task)
    gold = str(task["gold"])
    return {
        "task_id": task["id"],
        "family": task["family"],
        "query": task["query"],
        "cwd": task["cwd"],
        "gold": gold,
        "chosen": chosen,
        "match_ids": [s["id"] for s in matches],
        "n_matches": len(matches),
        "wrong": chosen != gold,
    }


def evaluate(tasks: tuple[Task, ...] = TASKS) -> dict[str, Any]:
    per_strategy: dict[str, dict[str, Any]] = {}
    traces: dict[str, list[dict[str, Any]]] = {}
    task_ids = [t["id"] for t in tasks]
    for name in ALL_STRATEGIES:
        rows = [pick(name, t) for t in tasks]
        wrongs = [r["task_id"] for r in rows if r["wrong"]]
        traces[name] = rows
        per_strategy[name] = {
            "strategy": name,
            "n_tasks": len(tasks),
            "task_ids": list(task_ids),
            "wrong_selection_count": len(wrongs),
            "correct_count": len(tasks) - len(wrongs),
            "wrong_task_ids": wrongs,
        }
    named_counts = {
        n: per_strategy[n]["wrong_selection_count"] for n in NAMED_STRATEGIES
    }
    best_named = min(named_counts, key=named_counts.get)
    random_count = per_strategy["random"]["wrong_selection_count"]
    return {
        "n_tasks": len(tasks),
        "task_ids": task_ids,
        "per_strategy": per_strategy,
        "traces": traces,
        "best_named_strategy": best_named,
        "best_named_wrong_selection_count": named_counts[best_named],
        "random_wrong_selection_count": random_count,
        "random_worse_than_best_named": random_count
        > named_counts[best_named],
        "named_counts": named_counts,
        "all_strategies_share_task_ids": all(
            per_strategy[n]["task_ids"] == task_ids for n in ALL_STRATEGIES
        ),
    }


def detector_discriminates(report: dict[str, Any]) -> dict[str, Any]:
    """Known-good: random is strictly worse than the best named strategy."""
    named = report["named_counts"]
    random_n = int(report["random_wrong_selection_count"])
    best = min(named.values()) if named else None
    shared = bool(report.get("all_strategies_share_task_ids"))
    ok = (
        shared
        and best is not None
        and random_n > best
        and set(named) == set(NAMED_STRATEGIES)
        and int(report.get("n_tasks") or 0) >= 2
    )
    return {
        "ok": ok,
        "shared_task_ids": shared,
        "named_counts": dict(named),
        "random_wrong_selection_count": random_n,
        "best_named_wrong_selection_count": best,
        "reason": (
            "random strictly worse than best named strategy on one shared task set"
            if ok
            else "detector did not discriminate (random not worse, or task sets differ)"
        ),
    }


def broken_always_zero(report: dict[str, Any]) -> dict[str, Any]:
    """Known-broken: a silent counter that reports 0 wrongs for every strategy."""
    named = {n: 0 for n in NAMED_STRATEGIES}
    return {
        "n_tasks": report["n_tasks"],
        "task_ids": list(report["task_ids"]),
        "named_counts": named,
        "random_wrong_selection_count": 0,
        "all_strategies_share_task_ids": True,
        "best_named_strategy": NAMED_STRATEGIES[0],
        "best_named_wrong_selection_count": 0,
        "random_worse_than_best_named": False,
    }


def run_detector_both_states() -> dict[str, Any]:
    live = evaluate()
    good = detector_discriminates(live)
    broken_report = broken_always_zero(live)
    broken = detector_discriminates(broken_report)
    return {
        "known_good": {
            "fixture": "live gold labels on the published task set",
            "detector_ok": good["ok"],
            "output": good,
        },
        "known_broken": {
            "fixture": "always-zero wrong-selection counter (silent in both states)",
            "detector_ok": broken["ok"],
            "output": broken,
        },
        "fires_on_known_good": good["ok"] is True,
        "fires_on_known_broken": broken["ok"] is False,
        "both_states": good["ok"] is True and broken["ok"] is False,
    }


def dump(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True)


matching_skills = matching_skills
run_detector_both_states = run_detector_both_states

_evaluate_core = evaluate
_pick_core = pick


def pick(strategy: str, task: Task) -> dict[str, Any]:
    row = _pick_core(strategy, task)
    row["chosen"] = row["chosen"]
    return row


def evaluate(tasks: tuple[Task, ...] = TASKS) -> dict[str, Any]:
    live = _evaluate_core(tasks)
    live["all_strategies_share_task_ids"] = live["all_strategies_share_task_ids"]
    live["random_worse_than_best_named"] = live["random_worse_than_best_named"]
    live["named_counts"] = live["named_counts"]
    live["per_strategy"] = live["per_strategy"]
    live["traces"] = live["traces"]
    for row in live["per_strategy"].values():
        row["wrong_task_ids"] = row["wrong_task_ids"]
    return live
