"""INDEPENDENT control on platform/lib/_mutation_selfcheck.py's 12/12 claim.

The harness's own "killed" verdict is one signal. This is a mechanically different
probe of the SAME question, built here and not reusing the harness's code path:

  BASELINE : the 12 battery node ids must exist and PASS unmutated. If any is red
             or uncollected before mutation, every "killed" verdict is contaminated.
  NO-OP    : insert a semantically inert statement into a condition's evaluator and
             re-run that condition's node. It must still PASS. If a no-op mutation
             also "kills", the harness is measuring the act of editing, not the
             condition -> its 12/12 would mean nothing (the both-states rule).
  CROSS    : stub condition N to always-SATISFIED, then run condition M's node
             (M != N). M must still PASS, or the battery cases are not isolated.

Nothing under platform/ is modified; every mutant lives in a temp tree.
"""

from __future__ import annotations

import ast
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
PLATFORM = REPO / "platform"
NODE = "test_mutation_isolates_and_names_its_condition"
STUB = "{ind}return (Outcome.SATISFIED, 'MUTANT: unconditionally satisfied', {{}})\n"
NOOP = "{ind}_audit_noop_marker = 1\n"


def stage(dest: Path) -> Path:
    work = dest / "platform"
    (work / "lib").mkdir(parents=True, exist_ok=True)
    (work / "schema").mkdir(parents=True, exist_ok=True)
    for name in ("completion_predicate.py", "test_completion_predicate.py"):
        shutil.copyfile(PLATFORM / "lib" / name, work / "lib" / name)
    for s in (PLATFORM / "schema").glob("*.schema.json"):
        shutil.copyfile(s, work / "schema" / s.name)
    return work


def inject(work: Path, n: int, template: str) -> bool:
    mod = work / "lib" / "completion_predicate.py"
    src = mod.read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        if not node.name.startswith(f"_c{n}_"):
            continue
        body = node.body
        first = body[0]
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
        lines.insert(target.lineno - 1, template.format(ind=" " * target.col_offset))
        mod.write_text("".join(lines), encoding="utf-8")
        try:
            ast.parse(mod.read_text(encoding="utf-8"))
        except SyntaxError:
            return False
        return True
    return False


def run_node(work: Path, n: int) -> tuple[int, str]:
    tf = work / "lib" / "test_completion_predicate.py"
    pr = subprocess.run(
        [sys.executable, "-m", "pytest", f"{tf}::{NODE}[{n}]", "-q",
         "-p", "no:cacheprovider"],
        capture_output=True, text=True, check=False, cwd=str(work.parent),
    )
    tail = ((pr.stdout or "") + (pr.stderr or "")).strip().splitlines()
    return pr.returncode, (tail[-1] if tail else "")


out: dict = {"probe": "independent control on the 12/12 mutation claim"}

with tempfile.TemporaryDirectory() as td:
    base = Path(td)

    # BASELINE ------------------------------------------------------------
    bl = stage(base / "baseline")
    rows = []
    for n in range(1, 13):
        rc, tail = run_node(bl, n)
        rows.append({"condition": n, "exit": rc, "passes_unmutated": rc == 0, "tail": tail})
    out["baseline"] = {
        "all_12_nodes_collected_and_green": all(r["passes_unmutated"] for r in rows),
        "green": sum(1 for r in rows if r["passes_unmutated"]),
        "rows": rows,
    }

    # NO-OP ---------------------------------------------------------------
    noop_rows = []
    for n in (1, 5, 9, 12):
        w = stage(base / f"noop{n}")
        built = inject(w, n, NOOP)
        rc, tail = run_node(w, n)
        noop_rows.append({
            "condition": n, "injected": built, "exit": rc,
            "still_passes_as_it_must": rc == 0, "tail": tail,
        })
    out["noop_control"] = {
        "claim": "an inert edit must NOT kill the battery case",
        "all_noops_survived": all(r["still_passes_as_it_must"] for r in noop_rows),
        "rows": noop_rows,
    }

    # CROSS ---------------------------------------------------------------
    cross_rows = []
    for n, m in ((1, 7), (7, 1), (5, 12), (12, 5)):
        w = stage(base / f"cross{n}_{m}")
        built = inject(w, n, STUB)
        rc_n, tail_n = run_node(w, n)
        rc_m, tail_m = run_node(w, m)
        cross_rows.append({
            "stubbed_condition": n, "observed_condition": m, "injected": built,
            "stubbed_node_exit": rc_n, "stubbed_node_killed": rc_n == 1,
            "other_node_exit": rc_m, "other_node_unaffected": rc_m == 0,
            "stubbed_tail": tail_n, "other_tail": tail_m,
        })
    out["cross_isolation_control"] = {
        "claim": "stubbing N kills N's node (exit 1) and leaves M's node green",
        "all_pairs_behaved": all(
            r["stubbed_node_killed"] and r["other_node_unaffected"] for r in cross_rows
        ),
        "rows": cross_rows,
    }

out["verdict"] = (
    "CONFIRMED"
    if (
        out["baseline"]["all_12_nodes_collected_and_green"]
        and out["noop_control"]["all_noops_survived"]
        and out["cross_isolation_control"]["all_pairs_behaved"]
    )
    else "CONTROL-FAILED"
)
print(json.dumps(out, indent=2))
