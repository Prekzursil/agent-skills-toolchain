#!/usr/bin/env python3
"""Blind discrimination test, independent of assign.py cue scoring.

A reader sees only a class definition and four unlabeled candidate `does`
texts (1 in-class, 3 out). It must pick the in-class one. Scoring here is
character 4-gram Jaccard — not cue-token overlap — so a taxonomy that only
looks separable under the assignment heuristic still fails this probe.

Coverage numbers are not to be trusted unless accuracy >= FLOOR.
A collapsed-definition mutant must fall below FLOOR (both-states).
"""
from __future__ import annotations

import hashlib
from typing import Any, Iterable

FLOOR = 0.80
NGRAM = 4
COLLAPSED_DEF = "a generic workflow that performs a task"


def char_ngrams(text: str, n: int = NGRAM) -> set[str]:
    s = "".join(ch.lower() for ch in text if ch.isalnum() or ch.isspace())
    s = " ".join(s.split())
    if len(s) < n:
        return {s} if s else set()
    return {s[i : i + n] for i in range(len(s) - n + 1)}


def jaccard(a: str, b: str) -> float:
    sa, sb = char_ngrams(a), char_ngrams(b)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def pick_in_class(class_def: str, options: list[dict[str, str]]) -> str:
    """Return the candidate_id with highest 4-gram Jaccard to class_def."""
    ranked = sorted(
        ((jaccard(class_def, opt["does"]), opt["id"]) for opt in options),
        key=lambda t: (-t[0], t[1]),
    )
    return ranked[0][1]


def _stable_pick(key: str, items: list[str], k: int) -> list[str]:
    scored = sorted(
        items,
        key=lambda x: hashlib.sha256(f"{key}:{x}".encode("utf-8")).hexdigest(),
    )
    return scored[:k]


def trial_sets(
    assignments: list[dict[str, Any]],
    classes_by_id: dict[str, dict],
    *,
    n_out: int = 3,
) -> list[dict[str, Any]]:
    """Build 4-choice trials for single-class planted (or otherwise assigned) rows."""
    in_class_pool: dict[str, list[str]] = {}
    does_by_id = {}
    for row in assignments:
        does_by_id[row["candidate_id"]] = row["does"]
        if len(row["class_ids"]) != 1:
            continue
        cid = row["class_ids"][0]
        in_class_pool.setdefault(cid, []).append(row["candidate_id"])
    all_ids = [row["candidate_id"] for row in assignments]
    trials = []
    for class_id, members in sorted(in_class_pool.items()):
        cls = classes_by_id[class_id]
        for member in members:
            outs = [
                oid
                for oid in all_ids
                if oid != member
                and class_id
                not in next(
                    r["class_ids"] for r in assignments if r["candidate_id"] == oid
                )
            ]
            if len(outs) < n_out:
                continue
            chosen_outs = _stable_pick(f"{class_id}:{member}", outs, n_out)
            options = [{"id": member, "does": does_by_id[member]}] + [
                {"id": oid, "does": does_by_id[oid]} for oid in chosen_outs
            ]
            options.sort(key=lambda o: o["id"])
            trials.append(
                {
                    "class_id": class_id,
                    "class_definition": cls["definition"],
                    "in_class_id": member,
                    "option_ids": [o["id"] for o in options],
                    "options": options,
                }
            )
    return trials


def run_trials(
    trials: list[dict[str, Any]],
    *,
    class_def_override: str | None = None,
) -> dict[str, Any]:
    results = []
    hits = 0
    for tr in trials:
        cdef = class_def_override if class_def_override is not None else tr["class_definition"]
        picked = pick_in_class(cdef, tr["options"])
        ok = picked == tr["in_class_id"]
        hits += int(ok)
        results.append(
            {
                "class_id": tr["class_id"],
                "in_class_id": tr["in_class_id"],
                "picked": picked,
                "correct": ok,
                "option_ids": tr["option_ids"],
            }
        )
    n = len(results)
    acc = (hits / n) if n else 0.0
    return {
        "n_trials": n,
        "hits": hits,
        "accuracy": acc,
        "floor": FLOOR,
        "floor_met": n > 0 and acc >= FLOOR,
        "results": results,
        "collapsed": class_def_override is not None,
    }


def discrimination_report(
    assignments: list[dict[str, Any]],
    classes: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    by_id = {c["id"]: c for c in classes}
    trials = trial_sets(assignments, by_id)
    live = run_trials(trials)
    collapsed = run_trials(trials, class_def_override=COLLAPSED_DEF)
    both_states = live["floor_met"] and (not collapsed["floor_met"])
    return {
        "scorer": "char-4gram-jaccard",
        "independent_of": "assign.score_class cue-token overlap",
        "floor": FLOOR,
        "live": {k: v for k, v in live.items() if k != "results"},
        "collapsed": {k: v for k, v in collapsed.items() if k != "results"},
        "both_states_ok": both_states,
        "coverage_numbers_reportable": live["floor_met"],
        "live_results": live["results"],
        "n_trials": live["n_trials"],
    }
