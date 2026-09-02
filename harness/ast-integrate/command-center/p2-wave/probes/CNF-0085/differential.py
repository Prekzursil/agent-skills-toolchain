#!/usr/bin/env python3
"""Compare runner fan-in vs reference oracle on the same corpus."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from corpus import ensure_fixtures, receipts, row_id_of
from oracle import evaluate_receipt as oracle_eval
from runner_fanin import evaluate_receipt as runner_eval
from spec import CONDITION_IDS
from stub import evaluate_receipt as stub_eval

Eval = Callable[[Any, Path], dict[str, Any]]


def _cell(row: Any, candidate: dict[str, Any], oracle: dict[str, Any]) -> dict[str, Any]:
    rid = row_id_of(row)
    cv, ov = candidate["verdict"], oracle["verdict"]
    cf, of_ = candidate["failing_condition_id"], oracle["failing_condition_id"]
    expect = None
    if isinstance(row, dict):
        expect = row.get("expect_failing_condition_id")
    elif not isinstance(row, dict):
        expect = "C1"
    return {
        "row_id": rid,
        "candidate_verdict": cv,
        "oracle_verdict": ov,
        "candidate_failing_condition_id": cf,
        "oracle_failing_condition_id": of_,
        "agree_verdict": cv == ov,
        "agree_failing_condition": cf == of_,
        "agree": cv == ov and cf == of_,
        "expected_failing_condition_id": expect,
        "candidate_reason": candidate.get("reason"),
        "oracle_reason": oracle.get("reason"),
        "oracle_condition_vector": oracle.get("condition_vector"),
    }


def compare(repo: Path, candidate: Eval, oracle: Eval = oracle_eval) -> list[dict[str, Any]]:
    ensure_fixtures(repo)
    table = []
    for row in receipts():
        table.append(_cell(row, candidate(row, repo), oracle(row, repo)))
    return table


def runner_vs_oracle(repo: Path) -> list[dict[str, Any]]:
    return compare(repo, runner_eval, oracle_eval)


def stub_vs_oracle(repo: Path) -> list[dict[str, Any]]:
    return compare(repo, stub_eval, oracle_eval)


def disagreements(table: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in table if not row["agree"]]


def expected_id_mismatches(table: list[dict[str, Any]]) -> list[dict[str, Any]]:
    bad = []
    for row in table:
        expect = row.get("expected_failing_condition_id")
        if expect is None and row["row_id"] == "all-satisfied":
            if row["oracle_verdict"] != "PASS" or row["candidate_verdict"] != "PASS":
                bad.append(row)
            continue
        if expect and (
            row["oracle_failing_condition_id"] != expect
            or row["candidate_failing_condition_id"] != expect
        ):
            bad.append(row)
    return bad


def distinct_fail_ids(table: list[dict[str, Any]]) -> list[str]:
    ids = []
    for row in table:
        cid = row["oracle_failing_condition_id"]
        if isinstance(cid, str) and cid not in ids:
            ids.append(cid)
    return ids


def per_condition_summary(table: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for cid in CONDITION_IDS:
        hits = [r["row_id"] for r in table if r["oracle_failing_condition_id"] == cid]
        out.append(
            {
                "condition_id": cid,
                "rows_first_fail": hits,
                "runner_oracle_agree_on_those_rows": all(
                    r["agree"]
                    for r in table
                    if r["oracle_failing_condition_id"] == cid
                ),
            }
        )
    return out
