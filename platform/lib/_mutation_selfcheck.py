"""Mutation test of the SHIPPED predicate: prove the battery goes RED when a condition is weakened.

The twelve-mutation battery in test_completion_predicate.py proves each condition rejects a
violating input. That is necessary but not sufficient: a suite that is green today might also be
green against a predicate whose evaluators were silently gutted, in which case the twelve passing
assertions would be measuring the fixtures rather than the code (the mutation-testing lesson from
rules/common/single-signal-verification.md 3b - a suite that stays green is not protecting that
behaviour).

So: copy platform/{lib,schema} to a throwaway tree, and for each of the twelve conditions rewrite
that ONE evaluator in the COPY to unconditionally return SATISFIED, then run only that condition's
battery case against the copy. Every mutant must be KILLED (the test must fail). A surviving mutant
names a condition whose test does not actually depend on the evaluator.

Nothing in the real tree is modified. Exits 0 only when 12/12 mutants are killed.
"""

from __future__ import annotations

import ast
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
PLATFORM = REPO_ROOT / "platform"

STUB_TEMPLATE = (
    "{ind}return (Outcome.SATISFIED, 'MUTANT: unconditionally satisfied', {{}})\n"
)

_NAME = re.compile(r"^_c(\d+)_")


def build_mutant(dest: Path, n: int) -> bool:
    """Rewrite condition ``n``'s evaluator in ``dest`` to always return SATISFIED.

    Uses the AST for the insertion point. A regex-driven first version inserted the stub four
    characters into the first body LINE whenever the function had no docstring, producing an
    IndentationError - and the harness then scored every mutant as "killed" because pytest exited
    non-zero on the collection error. That measured a syntax error, not the battery's sensitivity,
    so the kill criterion below now also requires the mutant to import cleanly.
    """
    module = dest / "lib" / "completion_predicate.py"
    src = module.read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        m = _NAME.match(node.name)
        if not m or int(m.group(1)) != n:
            continue
        body = node.body
        first = body[0]
        # Skip a leading docstring so the stub lands after it, not inside it.
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
            and len(body) > 1
        ):
            target = body[1]
        else:
            target = first
        lines = src.splitlines(keepends=True)
        stub = STUB_TEMPLATE.format(ind=" " * target.col_offset)
        lines.insert(target.lineno - 1, stub)
        module.write_text("".join(lines), encoding="utf-8")
        # Fail closed if the mutant is not even parseable.
        try:
            ast.parse(module.read_text(encoding="utf-8"))
        except SyntaxError:
            return False
        return True
    return False


def main() -> int:
    rows: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        for n in range(1, 13):
            work = base / f"m{n}" / "platform"
            (work / "lib").mkdir(parents=True, exist_ok=True)
            (work / "schema").mkdir(parents=True, exist_ok=True)
            # Copy ONLY this unit's files. A recursive copytree of platform/lib races sibling lanes
            # writing their own `*.tmp.<pid>.<hash>` files there and dies with WinError 2 - measured.
            for name in ("completion_predicate.py", "test_completion_predicate.py"):
                shutil.copyfile(PLATFORM / "lib" / name, work / "lib" / name)
            for schema in (PLATFORM / "schema").glob("*.schema.json"):
                shutil.copyfile(schema, work / "schema" / schema.name)
            if not build_mutant(work, n):
                rows.append({"condition": n, "mutant_built": False, "killed": False})
                continue

            # (a) the mutant must still IMPORT. Without this, a syntax error scores as a kill.
            imp = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "import completion_predicate as m; print(m.REDUCER_ID)",
                ],
                capture_output=True,
                text=True,
                check=False,
                cwd=str(work / "lib"),
            )
            importable = imp.returncode == 0

            testfile = work / "lib" / "test_completion_predicate.py"

            def run_node(nodeid: str) -> subprocess.CompletedProcess[str]:
                # Exact node id, not -k. A `-k "... and 9-"` expression collected ZERO tests
                # (pytest exit 5) because parametrize ids render as `[9]`, and the harness then
                # scored every mutant as a survivor - measured, and the reason -k is banned here.
                return subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "pytest",
                        nodeid,
                        "-q",
                        "-p",
                        "no:cacheprovider",
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                    cwd=str(work.parent),
                )

            # (b) the battery case for condition n must FAIL (exit 1), not error (exit 2+) and not
            #     silently collect nothing (exit 5).
            target = run_node(
                f"{testfile}::test_mutation_isolates_and_names_its_condition[{n}]"
            )
            t_out = target.stdout + target.stderr
            selected = target.returncode != 5 and "no tests ran" not in t_out
            failed_not_errored = (
                target.returncode == 1 and " error" not in t_out.splitlines()[-1]
            )

            # (c) an UNRELATED control test must still PASS, proving the mutant is a semantic
            #     weakening of one condition rather than a globally broken module.
            control = run_node(
                f"{testfile}::test_all_twelve_conditions_are_reported_in_spec_order"
            )
            control_passes = control.returncode == 0

            rows.append(
                {
                    "condition": n,
                    "mutant_built": True,
                    "mutant_importable": importable,
                    "tests_selected": selected,
                    "target_exit_code": target.returncode,
                    "target_failed_not_errored": failed_not_errored,
                    "unrelated_control_still_passes": control_passes,
                    "killed": bool(
                        importable
                        and selected
                        and failed_not_errored
                        and control_passes
                    ),
                    "tail": t_out.strip().splitlines()[-1] if t_out.strip() else "",
                }
            )

    killed = [r["condition"] for r in rows if r["killed"]]
    survived = [r["condition"] for r in rows if not r["killed"]]
    report = {
        "artifact": "platform/lib/_mutation_selfcheck.py output",
        "what": "each condition evaluator replaced by an unconditional SATISFIED in a throwaway copy",
        "killed_count": len(killed),
        "killed": killed,
        "survived": survived,
        "rows": rows,
    }
    print(json.dumps(report, indent=2))
    if len(killed) == 12:
        print("SUCCESS:predicate-mutation-selfcheck 12/12 mutants killed")
        return 0
    print(f"FAILED:predicate-mutation-selfcheck survivors={survived}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
