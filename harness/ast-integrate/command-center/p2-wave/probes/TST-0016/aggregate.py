#!/usr/bin/env python3
"""Fail-fast vs independent-check aggregating job runner (TST-0016).

GitHub Actions jobs stop at the first step with a non-zero exit (unless
continue-on-error / if: always()). Independent checks therefore hide every
later defect. This runner has two modes:

  fail_fast   — sequential short-circuit (GHA default)
  aggregate   — run every step whose *genuine* dependencies succeeded;
                skip only dependent steps; aggregate defects; exit red
                when any executed check is red
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable, Optional


@dataclass
class Outcome:
    exit_code: int
    defects: list[str] = field(default_factory=list)
    note: str = ""


@dataclass
class StepSpec:
    id: str
    depends_on: tuple[str, ...]
    fn: Callable[[], Outcome]
    continue_on_error: bool = False
    if_always: bool = False
    kind: str = "check"


@dataclass
class StepResult:
    id: str
    status: str
    exit_code: Optional[int]
    defects: list[str]
    kind: str
    note: str = ""


@dataclass
class RunResult:
    mode: str
    results: list[StepResult]
    exit_code: int
    defects: list[str]

    def executed(self) -> list[StepResult]:
        return [r for r in self.results if r.status == "executed"]

    def skipped_fail_fast(self) -> list[StepResult]:
        return [r for r in self.results if r.status == "skipped-fail-fast"]

    def skipped_dependency(self) -> list[StepResult]:
        return [r for r in self.results if r.status == "skipped-dependency"]

    def as_dict(self) -> dict:
        return {
            "mode": self.mode,
            "exit_code": self.exit_code,
            "defect_count": len(self.defects),
            "defects": list(self.defects),
            "executed_ids": [r.id for r in self.executed()],
            "skipped_fail_fast_ids": [r.id for r in self.skipped_fail_fast()],
            "skipped_dependency_ids": [r.id for r in self.skipped_dependency()],
            "results": [
                {
                    "id": r.id,
                    "status": r.status,
                    "exit_code": r.exit_code,
                    "defects": list(r.defects),
                    "kind": r.kind,
                    "note": r.note,
                }
                for r in self.results
            ],
        }


def _dep_ok(dep: StepResult) -> bool:
    if dep.status != "executed":
        return False
    if dep.exit_code in (0, None):
        return True
    return False


def run_job(steps: Iterable[StepSpec], mode: str) -> RunResult:
    if mode not in {"fail_fast", "aggregate"}:
        raise ValueError(f"unknown mode {mode!r}")
    specs = list(steps)
    results: list[StepResult] = []
    by_id: dict[str, StepResult] = {}
    fail_fast_tripped = False

    for spec in specs:
        skip_status = ""
        skip_note = ""
        if spec.if_always:
            pass
        elif mode == "fail_fast":
            if fail_fast_tripped:
                skip_status = "skipped-fail-fast"
                skip_note = "predecessor failed; GHA default short-circuit"
        else:
            missing = [d for d in spec.depends_on if d not in by_id]
            failed = [
                d
                for d in spec.depends_on
                if d in by_id and not _dep_ok(by_id[d])
            ]
            if missing or failed:
                skip_status = "skipped-dependency"
                skip_note = (
                    "genuine dependency unsatisfied: "
                    + ",".join(missing + failed)
                )

        if skip_status:
            row = StepResult(
                id=spec.id,
                status=skip_status,
                exit_code=None,
                defects=[],
                kind=spec.kind,
                note=skip_note,
            )
        else:
            out = spec.fn()
            row = StepResult(
                id=spec.id,
                status="executed",
                exit_code=int(out.exit_code),
                defects=list(out.defects),
                kind=spec.kind,
                note=out.note,
            )
            if (
                mode == "fail_fast"
                and row.exit_code != 0
                and not spec.continue_on_error
            ):
                fail_fast_tripped = True

        results.append(row)
        by_id[spec.id] = row

    defects: list[str] = []
    for row in results:
        defects.extend(row.defects)
    red = any(
        r.status == "executed" and r.exit_code not in (0, None) for r in results
    )
    return RunResult(
        mode=mode,
        results=results,
        exit_code=1 if red else 0,
        defects=defects,
    )
