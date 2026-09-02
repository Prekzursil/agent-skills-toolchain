"""Detector: fires when zero-history is ranked as if it had a measured score."""
from __future__ import annotations

from typing import Any

import store as S


def inspect(store: dict, ranking: dict) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    min_n = store["min_resolved_n"]
    for row in ranking.get("ranked") or []:
        pid = row["participant_id"]
        task = row["task_class"]
        n = S.resolved_n(store, pid, task)
        assigned = row.get("brier")
        if n < min_n:
            findings.append(
                {
                    "code": "ZERO_HISTORY_RANKED",
                    "participant_id": pid,
                    "task_class": task,
                    "resolved_n": n,
                    "assigned_brier": assigned,
                }
            )
        if n == 0 and assigned is not None:
            findings.append(
                {
                    "code": "INVENTED_SCORE_ON_RANKING",
                    "participant_id": pid,
                    "task_class": task,
                    "assigned_brier": assigned,
                }
            )
        if row.get("imputed") is True:
            findings.append(
                {
                    "code": "IMPUTED_FLAG",
                    "participant_id": pid,
                    "task_class": task,
                    "impute_source": row.get("impute_source"),
                }
            )
        rec = S.find_record(store, pid, task)
        if rec is not None and rec["brier"] is None and assigned is not None:
            findings.append(
                {
                    "code": "RANKING_SCORE_ABSENT_FROM_STORE",
                    "participant_id": pid,
                    "assigned_brier": assigned,
                }
            )
    return findings


def fires(store: dict, ranking: dict) -> bool:
    return len(inspect(store, ranking)) > 0


def both_states(store: dict, known_good: dict, planted_bad: dict) -> dict[str, Any]:
    good_findings = inspect(store, known_good)
    bad_findings = inspect(store, planted_bad)
    good_fires = len(good_findings) > 0
    bad_fires = len(bad_findings) > 0
    return {
        "known_good_fires": good_fires,
        "planted_bad_fires": bad_fires,
        "silent_on_good": not good_fires,
        "fires_on_bad": bad_fires,
        "discriminates": (not good_fires) and bad_fires,
        "known_good_findings": good_findings,
        "planted_bad_findings": bad_findings,
        "known_good_finding_count": len(good_findings),
        "planted_bad_finding_count": len(bad_findings),
    }


def verbatim_line(label: str, result: dict) -> str:
    return (
        f"{label} silent_on_good={result['silent_on_good']} "
        f"fires_on_bad={result['fires_on_bad']} "
        f"good_findings={result['known_good_finding_count']} "
        f"bad_findings={result['planted_bad_finding_count']} "
        f"discriminates={result['discriminates']}"
    )
