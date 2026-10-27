#!/usr/bin/env python3
"""Flake-rate ledger and quarantine lane for TST-0336.

Accounting rules (catalog TST-0336):
  * Measure per-test flake rate by rerunning N times on an unchanged commit.
  * A rate from N < 20 is labelled provisional.
  * A flake rate *above* 1-in-20 is a DEFECT against the test and is routed
    into a quarantine lane that still RUNS and still REPORTS but cannot block.
  * Quarantine is open debt: owner + age (and deadline) must be reported.
  * A retry policy that keeps only the last success absorbs flakes into
    invisible noise and is itself a DEFECT, never a pass.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

THRESHOLD = 1.0 / 20.0  # strictly above 1-in-20 is a defect
MIN_N_DEFINITIVE = 20
RETRY_ATTEMPTS_CATALOG = 3

TestFn = Callable[..., bool]


def parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    raw = ts.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def age_days(opened: datetime, now: datetime) -> float:
    return (now - opened).total_seconds() / 86400.0


def classify(outcomes: list[bool]) -> dict[str, Any]:
    """Classify first-attempt outcomes. Empty is a detector failure, not a pass."""
    n = len(outcomes)
    if n == 0:
        raise ValueError("classify: empty outcomes (no runs is not a zero flake rate)")
    passes = sum(1 for ok in outcomes if ok)
    fails = n - passes
    fail_rate = fails / n
    provisional = n < MIN_N_DEFINITIVE
    if fails == 0:
        classification = "DETERMINISTIC"
        flake_rate = 0.0
        quarantined = False
        can_block = False
    elif passes == 0:
        classification = "BROKEN"
        flake_rate = 0.0
        quarantined = False
        can_block = True
    else:
        classification = "FLAKY"
        flake_rate = fail_rate
        quarantined = flake_rate > THRESHOLD
        can_block = False
    return {
        "repetitions": n,
        "passes": passes,
        "fails": fails,
        "fail_rate": fail_rate,
        "flake_rate": flake_rate,
        "classification": classification,
        "provisional": provisional,
        "quarantined": quarantined,
        "can_block": can_block,
        "above_threshold": classification == "FLAKY" and flake_rate > THRESHOLD,
        "threshold": THRESHOLD,
    }


def run_one(fn: TestFn, run_index: int, max_attempts: int) -> list[bool]:
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")
    attempts: list[bool] = []
    for attempt in range(max_attempts):
        ok = bool(fn(run_index=run_index, attempt=attempt))
        attempts.append(ok)
        if ok:
            break
    return attempts


def retry_absorbed(first: list[bool], finals: list[bool]) -> bool:
    """True when retries turn a non-all-pass first attempt into an all-pass final."""
    if len(first) != len(finals) or not first:
        raise ValueError("retry_absorbed: mismatched or empty series")
    return (not all(first)) and all(finals)


@dataclass
class Debt:
    owner: str | None
    opened_at: str | None
    deadline: str | None
    age_days: float | None
    is_open: bool

    def complete(self) -> bool:
        if not self.is_open:
            return True
        return bool(self.owner) and self.age_days is not None

    def as_dict(self) -> dict[str, Any]:
        return {
            "owner": self.owner,
            "quarantine_opened_at": self.opened_at,
            "deadline": self.deadline,
            "age_days": self.age_days,
            "open": self.is_open,
            "complete": self.complete(),
        }


def debt_for(
    quarantined: bool,
    meta: dict[str, Any] | None,
    now: datetime,
) -> Debt:
    meta = meta or {}
    if not quarantined:
        return Debt(None, None, None, None, False)
    opened = parse_iso(meta.get("quarantine_opened_at")) or now
    return Debt(
        owner=meta.get("owner"),
        opened_at=opened.strftime("%Y-%m-%dT%H:%M:%SZ"),
        deadline=meta.get("deadline"),
        age_days=age_days(opened, now),
        is_open=True,
    )


def status_of(stats: dict[str, Any]) -> str:
    if stats["classification"] == "BROKEN":
        return "BROKEN"
    if stats["quarantined"]:
        return "QUARANTINED"
    if stats["classification"] == "FLAKY":
        return "FLAKY"
    return "PASS"


def measure_suite(
    tests: dict[str, TestFn],
    n: int,
    commit_sha: str,
    *,
    max_attempts: int = 1,
    now: datetime | None = None,
    registry: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Rerun each test n times at a fixed commit SHA.

    Flake accounting always uses first-attempt outcomes. max_attempts > 1 is
    only for proving that a retry policy would hide flakes — those finals
    must not replace the ledger.
    """
    if n < 1:
        raise ValueError("n must be >= 1")
    if not commit_sha:
        raise ValueError("commit_sha required (unchanged-commit contract)")
    now = now or datetime.now(timezone.utc)
    registry = registry or {}
    records: list[dict[str, Any]] = []
    ranked_src: list[dict[str, Any]] = []
    for test_id, fn in tests.items():
        per_run: list[list[bool]] = []
        for run_index in range(n):
            attempts = run_one(fn, run_index, max_attempts)
            per_run.append(attempts)
            for attempt_i, ok in enumerate(attempts):
                records.append(
                    {
                        "test_id": test_id,
                        "run_index": run_index,
                        "attempt": attempt_i,
                        "passed": ok,
                        "commit_sha": commit_sha,
                    }
                )
        first = [row[0] for row in per_run]
        stats = classify(first)
        debt = debt_for(stats["quarantined"], registry.get(test_id), now)
        row = {
            "test_id": test_id,
            "commit_sha": commit_sha,
            "status": status_of(stats),
            "outcomes_first_attempt": list(first),
            **stats,
            **debt.as_dict(),
        }
        ranked_src.append(row)
    shas = {rec["commit_sha"] for rec in records}
    if len(shas) != 1:
        raise RuntimeError(f"commit SHA was not held constant: {sorted(shas)}")
    ranked = sorted(ranked_src, key=lambda r: (-r["flake_rate"], r["test_id"]))
    defects = []
    for r in ranked:
        if r["above_threshold"]:
            defects.append(
                {
                    "kind": "DEFECT",
                    "target": "test",
                    "test_id": r["test_id"],
                    "reason": "flake-rate-above-1-in-20",
                    "flake_rate": r["flake_rate"],
                    "repetitions": r["repetitions"],
                    "provisional": r["provisional"],
                    "absorbed_as_retry": False,
                }
            )
    blockers = [r["test_id"] for r in ranked if r["can_block"]]
    return {
        "n": n,
        "commit_sha": commit_sha,
        "max_attempts": max_attempts,
        "accounting": "first-attempt",
        "threshold": THRESHOLD,
        "records": records,
        "ranked": ranked,
        "defects": defects,
        "suite_blockers": blockers,
        "suite_green": len(blockers) == 0,
        "quarantined_ids": [r["test_id"] for r in ranked if r["quarantined"]],
        "debt_incomplete": [
            r["test_id"] for r in ranked if r["quarantined"] and not r["complete"]
        ],
    }


def render_report(
    ranked: list[dict[str, Any]], *, hide_quarantined: bool = False
) -> list[dict[str, Any]]:
    """Quarantine lane still reports. hide_quarantined is the defective lane."""
    if hide_quarantined:
        return [r for r in ranked if not r.get("quarantined")]
    return list(ranked)


def quarantine_hidden(
    visible: list[dict[str, Any]], hidden: list[dict[str, Any]]
) -> bool:
    vis_q = {r["test_id"] for r in visible if r.get("quarantined")}
    hid_ids = {r["test_id"] for r in hidden}
    return bool(vis_q - hid_ids)


def retry_defects(
    tests: dict[str, TestFn],
    n: int,
    commit_sha: str,
    *,
    retry_attempts: int = RETRY_ATTEMPTS_CATALOG,
    now: datetime | None = None,
    registry: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Compare first-attempt ledger vs catalog N-attempt retry finals."""
    honest = measure_suite(
        tests, n, commit_sha, max_attempts=1, now=now, registry=registry
    )
    retried = measure_suite(
        tests,
        n,
        commit_sha,
        max_attempts=retry_attempts,
        now=now,
        registry=registry,
    )
    honest_by = {r["test_id"]: r for r in honest["ranked"]}
    out: list[dict[str, Any]] = []
    for test_id, row in honest_by.items():
        first = row["outcomes_first_attempt"]
        by_run: dict[int, list[bool]] = {}
        for rec in retried["records"]:
            if rec["test_id"] != test_id:
                continue
            by_run.setdefault(rec["run_index"], []).append(rec["passed"])
        finals = [by_run[i][-1] for i in range(n)]
        if retry_absorbed(first, finals):
            out.append(
                {
                    "kind": "DEFECT",
                    "target": "test",
                    "test_id": test_id,
                    "reason": "retry-absorbed-flake",
                    "first_attempt_flake_rate": row["flake_rate"],
                    "first_attempt_classification": row["classification"],
                    "retry_final_fail_rate": (
                        sum(1 for ok in finals if not ok) / len(finals)
                    ),
                    "retry_attempts": retry_attempts,
                    "policy": (
                        "A flake rate above 1-in-20 reruns is filed as a DEFECT "
                        "against the test, never absorbed as a retry."
                    ),
                }
            )
    return out
