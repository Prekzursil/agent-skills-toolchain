"""Measured KEEP/REVERT self-improvement loop (IMP-0255)."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

KEEP = "KEEP"
REVERT = "REVERT"
SOLVER_PATH = "solver.py"
ORIGINAL_SOLVER = "def solve(s):\n    return str(s).replace(' ', '_')\n"
HARMFUL_SOLVER = "def solve(s):\n    return 'BROKEN'\n"
NEUTRAL_SOLVER = ORIGINAL_SOLVER
IMPROVED_SOLVER = (
    "def solve(s):\n"
    "    return str(s).replace(' ', '_').replace('-', '_')\n"
)


@dataclass
class Case:
    id: str
    inp: str
    out: str


@dataclass
class Bench:
    cases: list[Case] = field(default_factory=list)


@dataclass
class ScoreRow:
    id: str
    passed: bool


@dataclass
class Score:
    rows: list[ScoreRow]
    passed: int
    total: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "total": self.total,
            "rows": [{"id": r.id, "passed": r.passed} for r in self.rows],
        }


@dataclass
class ChangeResult:
    decision: str
    reason: str = ""
    revert_observed: bool = False
    archived: bool = False
    archive_path: str | None = None
    promoted_case_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "reason": self.reason,
            "revert_observed": self.revert_observed,
            "archived": self.archived,
            "archive_path": self.archive_path,
            "promoted_case_ids": list(self.promoted_case_ids),
        }


class Tree:
    def __init__(self, files: dict[str, str] | None = None) -> None:
        self.files = dict(files or {SOLVER_PATH: ORIGINAL_SOLVER})

    def digest(self) -> str:
        blob = self.files.get(SOLVER_PATH, "")
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def write(self, path: str, content: str) -> None:
        self.files[path] = content


def _run_solver(solver: str, case: Case) -> bool:
    ns: dict[str, Any] = {}
    try:
        exec(solver, ns, ns)  # noqa: S102
        fn = ns.get("solve")
        if not callable(fn):
            return False
        return fn(case.inp) == case.out
    except Exception:
        return False


def independent_score(tree: Tree, bench: Bench) -> Score:
    solver = tree.files.get(SOLVER_PATH, "")
    rows = [ScoreRow(id=c.id, passed=_run_solver(solver, c)) for c in bench.cases]
    passed = sum(1 for r in rows if r.passed)
    return Score(rows=rows, passed=passed, total=len(rows))


def demo_fixtures() -> tuple[Tree, Bench, Bench]:
    frozen = Bench(
        cases=[
            Case("space", "hello world", "hello_world"),
            Case("plain", "abc", "abc"),
        ]
    )
    extra = Bench(cases=[Case("hyphen", "a-b", "a_b")])
    return Tree({SOLVER_PATH: ORIGINAL_SOLVER}), frozen, extra


def validate_change(
    tree: Tree,
    patch: dict[str, str],
    frozen: Bench,
    extra: Bench,
    archive_dir: str | Path | None = None,
    change_id: str = "change",
) -> ChangeResult:
    before = tree.digest()
    proposed = dict(tree.files)
    proposed.update(patch)
    trial = Tree(proposed)
    old = independent_score(tree, frozen)
    new = independent_score(trial, frozen)
    extra_old = independent_score(tree, extra) if extra.cases else Score([], 0, 0)
    extra_new = independent_score(trial, extra) if extra.cases else Score([], 0, 0)

    if new.passed < old.passed:
        return ChangeResult(decision=REVERT, reason="HARMFUL", revert_observed=tree.digest() == before)
    if extra.cases and extra_new.passed > extra_old.passed and new.passed >= old.passed:
        tree.files.update(patch)
        for case in extra.cases:
            if case.id not in {c.id for c in frozen.cases}:
                frozen.cases.append(case)
        archive_path = None
        archived = False
        if archive_dir is not None:
            dest = Path(archive_dir)
            dest.mkdir(parents=True, exist_ok=True)
            path = dest / f"{change_id}.py"
            path.write_text(patch.get(SOLVER_PATH, ""), encoding="utf-8")
            archive_path = str(path)
            archived = path.is_file()
        return ChangeResult(
            decision=KEEP,
            reason="IMPROVED",
            revert_observed=False,
            archived=archived,
            archive_path=archive_path,
            promoted_case_ids=[c.id for c in extra.cases],
        )
    return ChangeResult(decision=REVERT, reason="NEUTRAL", revert_observed=tree.digest() == before)
