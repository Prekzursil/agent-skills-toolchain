"""Oracle-first scoring for TST-0309 official ledger."""
from __future__ import annotations

from typing import Any

LINT_CODE = "ORACLE-FIRST-VIOLATION"


class OracleFirstViolation(Exception):
    def __init__(self, code: str = LINT_CODE, message: str = ""):
        super().__init__(message or code)
        self.code = code


def score_case(case: dict[str, Any], *, role: str = "official", judge_id: str | None = None, force_judge: bool = False) -> dict[str, Any]:
    from bench.judges import judge_label
    from bench.oracle import oracle_label

    overlap = case.get("overlap") is not False
    if force_judge:
        raise OracleFirstViolation(LINT_CODE, "official deterministic must not force a judge")
    if role == "official" and overlap:
        label = oracle_label(case)
        return {
            "case_id": case.get("id"),
            "label": label,
            "oracle_kind": "deterministic",
            "used_oracle": True,
            "role": role,
        }
    label = judge_label(case, judge_id or "judge-a")
    return {
        "case_id": case.get("id"),
        "label": label,
        "oracle_kind": "judged",
        "used_oracle": False,
        "role": role,
        "judge_id": judge_id,
    }


def score_corpus(cases: list[dict[str, Any]], *, role: str = "official", judge_id: str | None = None) -> list[dict[str, Any]]:
    return [score_case(c, role=role, judge_id=judge_id) for c in cases]


def plant_official_judge_score(case: dict[str, Any], judge_id: str) -> dict[str, Any]:
    from bench.judges import judge_label

    return {
        "case_id": case.get("id"),
        "label": judge_label(case, judge_id),
        "oracle_kind": "deterministic",
        "used_oracle": False,
        "role": "official",
        "judge_id": judge_id,
        "planted": True,
    }
