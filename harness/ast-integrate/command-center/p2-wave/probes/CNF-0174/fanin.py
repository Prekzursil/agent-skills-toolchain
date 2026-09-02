#!/usr/bin/env python3
"""Council-of-councils fan-in that surfaces nested completion disagreement.

Spec:11343 names 'nested councils disagree on completion' as a failure class.
The defect is fan-in averaging: a parent that emits one merged COMPLETE from
COMPLETE+BLOCKED children, with no trace of the split.

This module is the object under test for CNF-0174 because production
`tools/council/topology/nested.py` is absent on this worktree. It is not a
claim that B07 shipped a nested runtime.

Rules (detector ON):
- Parent applies the shared reducer (`reducer.judge`) to every child.
- A completion split is SURFACED: every child verdict is forwarded verbatim.
- Parent completion is never COMPLETE while a split exists.
- Minority reasoning is copied into the parent artifact.
- Persistent split (same fingerprint on retry) takes the declared escalation
  policy and terminates; it does not loop.
- Agreeing children fan in to that one verdict with no escalation.
- Duplicate child ids are a double-count defect, not silently merged.

Rules (detector OFF — known-broken control):
- Majority-mean averaging: COMPLETE=1.0 else 0.0; mean>=0.5 → COMPLETE.
- Child verdicts are overwritten with the merged verdict (split erased).
- Minority reports are dropped. This is the red state the control must catch.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Any

from reducer import COMPLETE, INCOMPLETE, MODULE_PATH, SYMBOL, judge

ESCALATION_POLICY = {
    "id": "cnf-0174-nested-completion-split",
    "on_first_split": "ESCALATE_TO_PARENT_WITH_SPLIT",
    "on_persistent_split": "ESCALATE_TO_OWNER_NO_LOOP",
    "max_attempts": 2,
    "never_loop": True,
}

PARENT_SPLIT = "SPLIT"


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def split_fingerprint(children: list[dict[str, Any]]) -> str:
    rows = [
        {"id": str(c.get("id")), "completion": str(c.get("completion") or "").upper()}
        for c in children
    ]
    rows.sort(key=lambda r: r["id"])
    return hashlib.sha256(canonical(rows).encode("utf-8")).hexdigest()


def _verbatim(child: dict[str, Any], judged: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": child.get("id"),
        "completion": judged["verdict"],
        "claimed_completion": child.get("completion"),
        "exit_code": child.get("exit_code"),
        "artifact_present": bool(child.get("artifact_present")),
        "reasoning": child.get("reasoning") or child.get("evidence") or "",
        "dissent": list(child.get("dissent") or []),
        "confidence": child.get("confidence"),
        "reducer_module": judged["reducer_module"],
        "reducer_symbol": judged["reducer_symbol"],
        "conditions": judged["conditions"],
    }


def _tally(children: list[dict[str, Any]]) -> dict[str, Any]:
    ids = [str(c.get("id")) for c in children]
    distinct = sorted(set(ids))
    by = Counter(str(c.get("completion") or "").upper() for c in children)
    return {
        "n_children": len(children),
        "distinct_source_ids": distinct,
        "n_distinct_sources": len(distinct),
        "double_counted": len(ids) != len(distinct),
        "by_completion": dict(sorted(by.items())),
    }


def detect_completion_split(judged_rows: list[dict[str, Any]]) -> dict[str, Any]:
    statuses = [str(r["completion"]) for r in judged_rows]
    unique = sorted(set(statuses))
    return {
        "split": len(unique) > 1,
        "unique_completions": unique,
        "n_unique": len(unique),
    }


def _average_away(children: list[dict[str, Any]], judged_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Known-broken path: silent consensus. Intentionally erases the split."""
    scores = [1.0 if r["completion"] == COMPLETE else 0.0 for r in judged_rows]
    mean = (sum(scores) / len(scores)) if scores else 0.0
    merged = COMPLETE if mean >= 0.5 else INCOMPLETE
    overwritten = [
        {
            "id": r["id"],
            "completion": merged,
            "claimed_completion": merged,
            "reasoning": "",
            "dissent": [],
            "erased": True,
        }
        for r in judged_rows
    ]
    return {
        "parent_verdict": merged,
        "parent_completion": merged,
        "split_surfaced": False,
        "averaged": True,
        "mean_completion": mean,
        "local_predicate_used": True,
        "local_predicate_name": "majority-mean-completion",
        "reducer_module": None,
        "escalation": None,
        "escalation_path": [],
        "terminal": True,
        "looped": False,
        "attempts": 1,
        "subcouncil_verdicts": overwritten,
        "minority_reports": [],
        "forwarded_dissent": [],
        "tally": _tally(children),
        "split_fingerprint": split_fingerprint(children),
        "split_meta": detect_completion_split(judged_rows),
    }


def fan_in(
    children: list[dict[str, Any]],
    *,
    split_detector: bool = True,
    attempt: int = 1,
    prior_fingerprint: str | None = None,
) -> dict[str, Any]:
    if not children:
        raise ValueError("fan_in requires at least one subcouncil")
    tally = _tally(children)
    if tally["double_counted"]:
        raise ValueError(
            f"double-counted subcouncil ids: {tally['distinct_source_ids']} "
            f"n={tally['n_children']}"
        )

    judged_rows = [_verbatim(c, judge(c)) for c in children]
    meta = detect_completion_split(judged_rows)
    fp = split_fingerprint(children)

    if not split_detector:
        broken = _average_away(children, judged_rows)
        broken["attempts"] = attempt
        return broken

    if not meta["split"]:
        parent = judged_rows[0]["completion"]
        return {
            "parent_verdict": parent,
            "parent_completion": parent,
            "split_surfaced": False,
            "averaged": False,
            "mean_completion": None,
            "local_predicate_used": False,
            "local_predicate_name": None,
            "reducer_module": MODULE_PATH,
            "reducer_symbol": SYMBOL,
            "escalation": None,
            "escalation_path": [],
            "terminal": True,
            "looped": False,
            "attempts": attempt,
            "subcouncil_verdicts": judged_rows,
            "minority_reports": [],
            "forwarded_dissent": [d for r in judged_rows for d in r["dissent"]],
            "tally": tally,
            "split_fingerprint": fp,
            "split_meta": meta,
        }

    counts = Counter(r["completion"] for r in judged_rows)
    majority_status, majority_n = counts.most_common(1)[0]
    minority = [r for r in judged_rows if r["completion"] != majority_status]
    persistent = prior_fingerprint == fp or attempt >= ESCALATION_POLICY["max_attempts"]
    if persistent:
        escalation = ESCALATION_POLICY["on_persistent_split"]
        path = [
            "observe-split",
            ESCALATION_POLICY["on_first_split"],
            "retry-same-fingerprint",
            ESCALATION_POLICY["on_persistent_split"],
        ]
        terminal = True
    else:
        escalation = ESCALATION_POLICY["on_first_split"]
        path = ["observe-split", ESCALATION_POLICY["on_first_split"]]
        terminal = False

    return {
        "parent_verdict": PARENT_SPLIT,
        "parent_completion": INCOMPLETE,
        "split_surfaced": True,
        "averaged": False,
        "mean_completion": None,
        "local_predicate_used": False,
        "local_predicate_name": None,
        "reducer_module": MODULE_PATH,
        "reducer_symbol": SYMBOL,
        "escalation": escalation,
        "escalation_path": path,
        "terminal": terminal,
        "looped": False,
        "attempts": attempt,
        "majority_status": majority_status,
        "majority_n": majority_n,
        "subcouncil_verdicts": judged_rows,
        "minority_reports": [
            {
                "id": r["id"],
                "completion": r["completion"],
                "reasoning": r["reasoning"],
                "dissent": r["dissent"],
                "lost": False,
            }
            for r in minority
        ],
        "forwarded_dissent": [d for r in judged_rows for d in r["dissent"]],
        "tally": tally,
        "split_fingerprint": fp,
        "split_meta": meta,
        "policy": ESCALATION_POLICY,
    }


def fan_in_until_terminal(
    children: list[dict[str, Any]],
    *,
    split_detector: bool = True,
    safety_cap: int = 8,
) -> dict[str, Any]:
    """Retry a persistent split until the policy terminates. Must not loop."""
    prior = None
    last: dict[str, Any] | None = None
    for attempt in range(1, safety_cap + 1):
        last = fan_in(
            children,
            split_detector=split_detector,
            attempt=attempt,
            prior_fingerprint=prior,
        )
        prior = last["split_fingerprint"]
        if last.get("terminal"):
            last["history_attempts"] = attempt
            last["hit_safety_cap"] = False
            return last
    assert last is not None
    last["looped"] = True
    last["hit_safety_cap"] = True
    last["history_attempts"] = safety_cap
    last["escalation"] = ESCALATION_POLICY["on_persistent_split"]
    last["terminal"] = True
    return last
