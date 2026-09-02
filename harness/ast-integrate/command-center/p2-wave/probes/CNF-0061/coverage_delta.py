#!/usr/bin/env python3
"""Line-set coverage delta for CNF-0061.

A percentage is a ratio. It can stay put while the covered LINE SET moves
(one file's lines traded for another's). This module:

  * runs selected tests under sys.settrace (coverage actually enabled)
  * diffs covered line sets, not percentages
  * classifies newly uncovered lines as security / rollback / neither
  * implements the delete-one-test detector control
  * reports threshold-file absence as NOT-CHECKED, never as a pass
"""
from __future__ import annotations

import ast
import dis
import importlib.util
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SUBJECT = HERE / "fixtures" / "subject"
TESTS = HERE / "fixtures" / "tests"

TEST_AUTH = "test_auth"
TEST_ROLLBACK = "test_rollback"
TEST_LEDGER = "test_ledger"
TEST_LEDGER_EXTRA = "test_ledger_extra"

TRADE_BEFORE = (TEST_AUTH, TEST_ROLLBACK, TEST_LEDGER)
TRADE_AFTER = (TEST_ROLLBACK, TEST_LEDGER, TEST_LEDGER_EXTRA)
FULL_SUITE = (TEST_AUTH, TEST_ROLLBACK, TEST_LEDGER, TEST_LEDGER_EXTRA)
DELETE_ONE = TEST_ROLLBACK

SECURITY_FILES = frozenset({"auth.py"})
ROLLBACK_FILES = frozenset({"rollback.py"})

THRESHOLD_NAMES = (
    ".coverage-thresholds.json",
    "coverage-thresholds.json",
    ".coverage_thresholds.json",
)

SKIP_DIRS = frozenset(
    {
        ".git",
        "node_modules",
        ".venv",
        "venv",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        "dist",
        "build",
        ".tox",
    }
)


@dataclass
class LineHitMap:
    hits: dict[str, set[int]] = field(default_factory=dict)
    coverage_enabled: bool = False
    traced_events: int = 0

    def add(self, rel: str, lineno: int) -> None:
        self.hits.setdefault(rel, set()).add(int(lineno))


def executable_lines(path: Path) -> set[int]:
    """Lines the interpreter can stop on (bytecode linestarts)."""
    src = path.read_text(encoding="utf-8")
    code = compile(src, str(path), "exec")
    lines: set[int] = set()
    stack = [code]
    while stack:
        c = stack.pop()
        for inst in dis.get_instructions(c):
            if inst.starts_line:
                lines.add(int(inst.starts_line))
        stack.extend(k for k in c.co_consts if hasattr(k, "co_code"))
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return lines
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            body = list(node.body)
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(getattr(body[0], "value", None), ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                lines.discard(int(body[0].lineno))
    return lines


def subject_executable() -> dict[str, set[int]]:
    out: dict[str, set[int]] = {}
    for path in sorted(SUBJECT.glob("*.py")):
        if path.name.startswith("_"):
            continue
        out[path.name] = executable_lines(path)
    return out


class _Tracer:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.hits = LineHitMap(coverage_enabled=True)
        self._cache: dict[str, str | None] = {}

    def _rel(self, filename: str) -> str | None:
        if filename in self._cache:
            return self._cache[filename]
        try:
            p = Path(filename).resolve()
            rel = p.relative_to(self.root).as_posix()
        except (OSError, ValueError):
            self._cache[filename] = None
            return None
        if not rel.endswith(".py") or rel.startswith(".."):
            self._cache[filename] = None
            return None
        self._cache[filename] = rel
        return rel

    def __call__(self, frame, event, arg):  # type: ignore[no-untyped-def]
        if event == "call":
            return self
        if event != "line":
            return self
        rel = self._rel(frame.f_code.co_filename)
        if rel is not None:
            self.hits.traced_events += 1
            self.hits.add(rel, int(frame.f_lineno))
        return self


def _load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _purge_prefix(prefixes: tuple[str, ...]) -> None:
    doomed = [k for k in list(sys.modules) if k.startswith(prefixes)]
    for k in doomed:
        sys.modules.pop(k, None)


def run_suite(
    test_names: Iterable[str],
    *,
    coverage_enabled: bool,
) -> tuple[LineHitMap, list[str]]:
    """Import and call test_* functions. Optionally install a line tracer."""
    names = list(test_names)
    subject_root = SUBJECT.resolve()
    tests_root = TESTS.resolve()
    inserted = []
    for p in (str(subject_root), str(tests_root)):
        if p not in sys.path:
            sys.path.insert(0, p)
            inserted.append(p)

    tracer: _Tracer | None = None
    prev = None
    executed: list[str] = []
    try:
        _purge_prefix(
            (
                "auth",
                "rollback",
                "ledger",
                "extra",
                "test_auth",
                "test_rollback",
                "test_ledger",
            )
        )
        if coverage_enabled:
            tracer = _Tracer(subject_root)
            prev = sys.gettrace()
            sys.settrace(tracer)
        for tname in names:
            path = tests_root / f"{tname}.py"
            if not path.is_file():
                raise FileNotFoundError(path)
            uniq = f"cnf0061_{tname}_{id(coverage_enabled)}_{len(executed)}"
            mod = _load_module(path, uniq)
            for attr in sorted(dir(mod)):
                if not attr.startswith("test_"):
                    continue
                fn = getattr(mod, attr)
                if not callable(fn):
                    continue
                fn()
                executed.append(f"{tname}.{attr}")
    finally:
        if coverage_enabled:
            sys.settrace(prev)
        for p in inserted:
            try:
                sys.path.remove(p)
            except ValueError:
                pass
        _purge_prefix(("auth", "rollback", "ledger", "extra", "cnf0061_"))

    if tracer is None:
        return LineHitMap(coverage_enabled=False), executed
    return tracer.hits, executed


def covered_pairs(
    hits: LineHitMap, executable: dict[str, set[int]]
) -> set[tuple[str, int]]:
    out: set[tuple[str, int]] = set()
    for rel, lines in executable.items():
        got = hits.hits.get(rel, set())
        for n in lines:
            if n in got:
                out.add((rel, n))
    return out


def percent(covered: set[tuple[str, int]], executable: dict[str, set[int]]) -> float:
    total = sum(len(v) for v in executable.values())
    if total == 0:
        return 0.0
    return round(100.0 * len(covered) / total, 4)


def classify_line(rel: str) -> str:
    name = Path(rel).name
    if name in SECURITY_FILES:
        return "security"
    if name in ROLLBACK_FILES:
        return "rollback"
    return "neither"


def file_line(rel: str, lineno: int) -> str:
    return f"{rel}:{lineno}"


def pairs_to_rows(pairs: Iterable[tuple[str, int]]) -> list[dict[str, Any]]:
    rows = []
    for rel, n in sorted(pairs):
        kind = classify_line(rel)
        rows.append(
            {
                "file": rel,
                "line": n,
                "file_line": file_line(rel, n),
                "path_class": kind,
                "in_security_or_rollback_path": kind in {"security", "rollback"},
            }
        )
    return rows


def snapshot(
    test_names: Iterable[str],
    *,
    coverage_enabled: bool,
    label: str,
) -> dict[str, Any]:
    executable = subject_executable()
    hits, executed = run_suite(test_names, coverage_enabled=coverage_enabled)
    covered = covered_pairs(hits, executable) if coverage_enabled else set()
    pct = percent(covered, executable) if coverage_enabled else None
    return {
        "label": label,
        "tests": list(test_names),
        "executed_test_fns": executed,
        "coverage_enabled": bool(coverage_enabled and hits.coverage_enabled),
        "traced_events": hits.traced_events,
        "executable_line_count": sum(len(v) for v in executable.values()),
        "covered_line_count": len(covered),
        "percent": pct,
        "covered_lines": [file_line(r, n) for r, n in sorted(covered)],
        "executable_by_file": {k: sorted(v) for k, v in sorted(executable.items())},
    }


def delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    b = set(before.get("covered_lines") or [])
    a = set(after.get("covered_lines") or [])
    lost = sorted(b - a)
    gained = sorted(a - b)

    def parse(fl: str) -> tuple[str, int]:
        rel, _, num = fl.rpartition(":")
        return rel, int(num)

    lost_rows = pairs_to_rows(parse(x) for x in lost)
    gained_rows = pairs_to_rows(parse(x) for x in gained)
    sec = [r for r in lost_rows if r["path_class"] == "security"]
    rb = [r for r in lost_rows if r["path_class"] == "rollback"]
    bp = before.get("percent")
    ap = after.get("percent")
    pct_unchanged = bp is not None and ap is not None and bp == ap
    return {
        "newly_uncovered": lost_rows,
        "newly_uncovered_file_lines": lost,
        "newly_uncovered_count": len(lost),
        "newly_covered": gained_rows,
        "newly_covered_file_lines": gained,
        "newly_covered_count": len(gained),
        "percentage_side_by_side": {"before": bp, "after": ap, "unchanged": pct_unchanged},
        "line_set_changed": bool(lost or gained),
        "coverage_moved_without_percentage_moving": bool(
            pct_unchanged and (lost or gained)
        ),
        "security_path_newly_uncovered": sec,
        "rollback_path_newly_uncovered": rb,
        "any_security_or_rollback_newly_uncovered": bool(sec or rb),
    }


def find_threshold_files(root: Path) -> list[str]:
    """Project-level threshold files only. Never walk the whole tree.

    A repo-wide rglob treats other units' fixtures and vendor templates as
    this project's coverage SSOT, and does not finish on this worktree.
    The catalog question is: does THIS project have a thresholds file?
    Absence at the repo root (and this unit's fixture) is NOT-CHECKED.
    """
    found: list[str] = []
    for name in THRESHOLD_NAMES:
        p = root / name
        if p.is_file():
            found.append(name)
    fixture_root = HERE / "fixtures"
    if fixture_root.is_dir():
        for p in fixture_root.rglob("*"):
            if p.is_file() and p.name in THRESHOLD_NAMES:
                try:
                    found.append(p.relative_to(root).as_posix())
                except ValueError:
                    found.append(str(p))
    return sorted(set(found))


def live_coverage_data_files(root: Path) -> list[str]:
    """Line-granularity coverage data at the project root only.

    Two-state product comparison is NOT-CHECKED when no pair exists here.
    A repo-wide rglob is not a coverage instrument and does not finish.
    """
    names = (
        ".coverage",
        "coverage.xml",
        "coverage.json",
        "lcov.info",
        ".coverage.lcov",
    )
    found: list[str] = []
    for name in names:
        p = root / name
        if p.is_file():
            found.append(name)
    return found


def threshold_verdict(root: Path) -> dict[str, Any]:
    files = find_threshold_files(root)
    if not files:
        return {
            "question": "Does the project enforce a coverage threshold?",
            "verdict": "NOT-CHECKED",
            "reason": (
                "no .coverage-thresholds.json (or equivalent) on this worktree; "
                "absence is reported as NOT-CHECKED, never folded into a pass"
            ),
            "files": [],
        }
    return {
        "question": "Does the project enforce a coverage threshold?",
        "verdict": "PRESENT",
        "reason": (
            "threshold file(s) found; not treated as a silent pass of the "
            "line-set question"
        ),
        "files": files,
    }


def measure_all() -> dict[str, Any]:
    executable = subject_executable()
    before = snapshot(TRADE_BEFORE, coverage_enabled=True, label="before")
    after = snapshot(TRADE_AFTER, coverage_enabled=True, label="after")
    trade = delta(before, after)

    full = snapshot(FULL_SUITE, coverage_enabled=True, label="control-full")
    reduced_names = tuple(t for t in FULL_SUITE if t != DELETE_ONE)
    reduced = snapshot(reduced_names, coverage_enabled=True, label="control-delete-one")
    control = delta(full, reduced)

    blind_full = snapshot(FULL_SUITE, coverage_enabled=False, label="no-coverage-full")
    blind_reduced = snapshot(
        reduced_names, coverage_enabled=False, label="no-coverage-delete-one"
    )
    blind = delta(blind_full, blind_reduced)

    return {
        "executable": {k: sorted(v) for k, v in executable.items()},
        "before": before,
        "after": after,
        "trade": trade,
        "control_full": full,
        "control_reduced": reduced,
        "control": control,
        "without_coverage_full": blind_full,
        "without_coverage_reduced": blind_reduced,
        "without_coverage": blind,
        "deleted_test": DELETE_ONE,
        "coverage_enabled_both_trade_runs": bool(
            before["coverage_enabled"] and after["coverage_enabled"]
        ),
        "coverage_enabled_both_control_runs": bool(
            full["coverage_enabled"] and reduced["coverage_enabled"]
        ),
        "traced_events_trade": before["traced_events"] + after["traced_events"],
        "traced_events_control": full["traced_events"] + reduced["traced_events"],
    }


def assert_detector_invariants(m: dict[str, Any]) -> list[str]:
    """Return failures; empty means the detector is live."""
    fails: list[str] = []
    if not m.get("coverage_enabled_both_trade_runs"):
        fails.append("trade runs did not both enable coverage")
    if not m.get("coverage_enabled_both_control_runs"):
        fails.append("control runs did not both enable coverage")
    if int(m["before"].get("traced_events") or 0) <= 0:
        fails.append("before-state tracer recorded zero line events")
    if int(m["after"].get("traced_events") or 0) <= 0:
        fails.append("after-state tracer recorded zero line events")
    trade = m["trade"]
    if not trade.get("line_set_changed"):
        fails.append("trade did not change the covered line set")
    if not trade.get("coverage_moved_without_percentage_moving"):
        fails.append(
            "trade did not keep percentage unchanged while moving the line set "
            f"(side_by_side={trade.get('percentage_side_by_side')})"
        )
    if not trade.get("any_security_or_rollback_newly_uncovered"):
        fails.append("trade newly-uncovered set missed security/rollback paths")
    control = m["control"]
    if int(control.get("newly_uncovered_count") or 0) <= 0:
        fails.append("delete-one-test control produced an empty newly-uncovered set")
    if not any(
        r["path_class"] == "rollback" for r in control.get("newly_uncovered") or []
    ):
        fails.append("delete-one-test control did not uncover rollback-path lines")
    blind = m["without_coverage"]
    if int(blind.get("newly_uncovered_count") or 0) != 0:
        fails.append("run without coverage claimed a newly-uncovered set (must be blind)")
    if m["without_coverage_full"].get("coverage_enabled"):
        fails.append("without_coverage_full reported coverage_enabled=true")
    if m["without_coverage_reduced"].get("coverage_enabled"):
        fails.append("without_coverage_reduced reported coverage_enabled=true")
    return fails


def main() -> int:
    m = measure_all()
    fails = assert_detector_invariants(m)
    print(
        json.dumps(
            {
                "fails": fails,
                "summary": {
                    "trade_pct": m["trade"]["percentage_side_by_side"],
                    "trade_lost": m["trade"]["newly_uncovered_file_lines"],
                    "control_lost": m["control"]["newly_uncovered_file_lines"],
                    "blind_lost": m["without_coverage"]["newly_uncovered_count"],
                    "coverage_both": m["coverage_enabled_both_trade_runs"],
                },
            },
            indent=2,
            sort_keys=True,
        )
    )
    if fails:
        print("FAILED:CNF-0061 detector invariants")
        for f in fails:
            print(" ", f)
        return 1
    print("SUCCESS:CNF-0061 detector invariants")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
